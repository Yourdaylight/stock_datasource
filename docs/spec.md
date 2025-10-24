# 本地财经数据库（A股/港股·占位） · ClickHouse + TuShare · Airflow 编排 · spec.md

> 版本：v1.1（含 **Schema-on-API 动态表构建** / ODS 自动演进）
> 决策要点：A股使用**原子接口**；历史回填 **2020-01-01→今日**；日更调度 **18:00 Asia/Shanghai**；不复权为主表；并发仅做速率限制（不超过积分档限制）；失败任务入表记录；与交易日/公告对齐行数并做涨跌停/停复牌一致性 DQ；港股沿用 TuShare `ts_code` 规范且当前仅占位；权限控制暂缓（后续对外 API 再启用）。

---

## 0. 目标与边界
- **目标**：每日 18:00 自动从 TuShare 拉取 **A股**行情与指标入 ClickHouse；提供不复权主表、复权因子、每日指标与 DQ；支持从 **2020-01-01** 起的历史回填。  
- **港股**：当前 `hk_daily` 权限仅 **10 次/日** → **不执行批量拉取**，仅保留表结构与调度占位。  
- **非目标**：分钟级实时行情、撮合、外部鉴权 API（后续阶段处理）。

---

## 1. 架构总览

```
TuShare(REST)
   └─(raw json)──> Ingestion(Extractor)
        └─> ODS(自动建表/扩列, Schema-on-API)
             └─> DM/Fact(稳定业务表)
                  ├─ DQ 校验（行数/涨跌停/停复牌…
                  ├─ 物化/视图（复权/常用查询）
                  └─ 元数据/失败任务/Schema审计

Airflow
   ├─ DAG: daily_cn_1800（A股日更 18:00）
   ├─ DAG: backfill_cn_2020（历史回填）
   └─ DAG: hk_placeholders（港股占位）
```

---

## 2. TuShare 策略与额度
- 账户：2000 积分档；**控制每分钟调用 ≤ 限额**（建议限流 120–150/min，峰值不超 200/min）。  
- **A股原子接口**：`trade_cal`、`stock_basic`、`daily`、`adj_factor`、`daily_basic`、`suspend_d`、`stk_limit`。  
- **港股**：`hk_basic`、`hk_daily` 仅占位（不批量调用）。  
- 失败/超时/429：指数退避；调用封装统一节流器。

---

## 3. 数据模型（ClickHouse）

### 3.1 命名与通用规范
- 层级与前缀：  
  - **ODS 层**（接口直落，动态表）：`ods_<api>`（例 `ods_daily`）  
  - **DM/Fact 层**（稳定业务表）：`dim_*`、`fact_*`、`vw_*`  
  - **Meta**：`meta_*`  
- 分区：优先 `toYYYYMM(trade_date)`；无日期字段的按 `_ingested_at`。  
- 排序键：常规 `(ts_code, trade_date)` 或 `(market, ts_code, trade_date)`。  
- 幂等：`ReplacingMergeTree(version)`；`version = toUnixTimestamp(now())` 或源端更新标识。

### 3.2 **Schema-on-API 动态表构建（ODS 层）**
> 目标：**不写死列**；随 TuShare 字段**自动建表/扩列/宽化**；建表/扩列后**自动输出表结构**。详见 §5。

- ODS 表示例（初始由 Schema 同步任务自动生成）：
```sql
CREATE TABLE IF NOT EXISTS ods_daily (
  ts_code LowCardinality(String),
  trade_date Date,
  open Nullable(Float64), high Nullable(Float64),
  low Nullable(Float64), close Nullable(Float64),
  pre_close Nullable(Float64), change Nullable(Float64), pct_chg Nullable(Float64),
  vol Nullable(Float64), amount Nullable(Float64),
  version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
  _ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date);
```

- 自动扩列示例：
```sql
ALTER TABLE ods_daily
ADD COLUMN IF NOT EXISTS extra_col Nullable(Float64) AFTER amount;
```

- 宽化示例（Int → Float、非空 → 可空）：
```sql
ALTER TABLE ods_daily
MODIFY COLUMN open Nullable(Float64);
```

### 3.3 DM/Fact（稳定业务表，供消费方使用）
> ODS 动态、Fact 稳定：ODS 的新增列不会扰动下游；需要时通过 `INSERT SELECT` 补充映射。

```sql
-- 证券基础
CREATE TABLE IF NOT EXISTS dim_security (
  ts_code String,
  market LowCardinality(String) DEFAULT 'CN',  -- 'CN'|'HK'
  ticker String,
  name String,
  list_date Date,
  delist_date Nullable(Date),
  status LowCardinality(String),
  created_at DateTime DEFAULT now(),
  updated_at DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYear(list_date)
ORDER BY (market, ts_code);
```
（其余表定义同上省略）

---

## 4. 元数据、失败任务与 DQ

```sql
CREATE TABLE IF NOT EXISTS meta_ingestion_log (...);
CREATE TABLE IF NOT EXISTS meta_failed_task (...);
CREATE TABLE IF NOT EXISTS meta_quality_check (...);
```

---

## 5. **Schema-on-API 动态表构建（DTB）**

### 5.1 元数据表
```sql
CREATE TABLE IF NOT EXISTS meta_schema_catalog (...);
CREATE TABLE IF NOT EXISTS meta_schema_changelog (...);
CREATE TABLE IF NOT EXISTS meta_table_lock (...);
```

### 5.2 类型推断与宽化规则
（略，同前）

### 5.3 算法流程（Airflow Task：`schema_sync_<api>`）
1. 抽样探测  
2. 生成目标列  
3. DDL 计划  
4. 执行与登记  
5. 输出表结构  
6. 不兼容变化记录 `WIDEN_TYPE_FAILED`  

---

## 6. DQ 业务规则（核心）
- 行数与交易日对齐  
- 涨跌停边界  
- 停复牌一致性  
- 复权因子稳定性  

---

## 7. 调度与作业（Airflow）
- DAG: `daily_cn_1800`  
- DAG: `backfill_cn_2020`  
- DAG: `hk_placeholders`  

---

## 8. 采集与加载策略
- Extractor: 节流+重试  
- Loader: ODS → Fact (`INSERT SELECT`)  
- 幂等：`ReplacingMergeTree(version)`  

---

## 9. 查询与性能（NFR）
（同前）

---

## 10. 运维（Runbook 摘要）
- 失败补偿  
- 回填  
- 容量估算  

---

## 11. 安全与权限
（同前）

---

## 12. 字段映射（ODS→Fact · 节选）
| 源接口 | ODS 表 | Fact 表 | 关键映射 |
|---|---|---|---|
| `daily` | `ods_daily` | `fact_daily_bar` | ... |

---

## 13. 测试计划
1. 单日端到端  
2. 幂等重跑  
3. Schema 演进  
4. 失败注入  
5. 回填窗口  

---

## 14. 路线图
- Phase 1：A股流水线 + ODS 动态 Schema  
- Phase 2：公司行为、ClickHouse 集群化  
- Phase 3：对外查询 API（RBAC/JWT）
