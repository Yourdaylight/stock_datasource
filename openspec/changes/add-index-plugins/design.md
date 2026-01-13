# Design: 指数插件技术设计

## 架构概述

指数插件采用与现有tushare_daily插件相同的架构模式，继承`BasePlugin`基类，实现ETL流程。

## 插件设计

### 1. tushare_idx_factor_pro

**API接口**: `idx_factor_pro`

**表结构**: `ods_idx_factor_pro`

**字段列表**（约100个）:
- 基础行情：ts_code, trade_date, open, high, low, close, pre_close, change, pct_change, vol, amount
- 技术指标：asi_bfq, asit_bfq, atr_bfq, bbi_bfq, bias1_bfq, bias2_bfq, bias3_bfq, 
  boll_lower_bfq, boll_mid_bfq, boll_upper_bfq, brar_ar_bfq, brar_br_bfq, cci_bfq, cr_bfq,
  dfma_dif_bfq, dfma_difma_bfq, dmi_adx_bfq, dmi_adxr_bfq, dmi_mdi_bfq, dmi_pdi_bfq,
  downdays, updays, dpo_bfq, madpo_bfq, ema_bfq_5, ema_bfq_10, ema_bfq_20, ema_bfq_30,
  ema_bfq_60, ema_bfq_90, ema_bfq_250, emv_bfq, maemv_bfq, expma_12_bfq, expma_50_bfq,
  kdj_bfq, kdj_d_bfq, kdj_k_bfq, ktn_down_bfq, ktn_mid_bfq, ktn_upper_bfq, lowdays,
  topdays, ma_bfq_5, ma_bfq_10, ma_bfq_20, ma_bfq_30, ma_bfq_60, ma_bfq_90, ma_bfq_250,
  macd_bfq, macd_dea_bfq, macd_dif_bfq, mass_bfq, ma_mass_bfq, mfi_bfq, mtm_bfq, mtmma_bfq,
  obv_bfq, psy_bfq, psyma_bfq, roc_bfq, maroc_bfq, rsi_bfq_6, rsi_bfq_12, rsi_bfq_24,
  taq_down_bfq, taq_mid_bfq, taq_up_bfq, trix_bfq, trma_bfq, vr_bfq, wr_bfq, wr1_bfq,
  xsii_td1_bfq, xsii_td2_bfq, xsii_td3_bfq, xsii_td4_bfq
- 系统字段：version, _ingested_at

**分区策略**: 按月分区 `toYYYYMM(trade_date)`

**排序键**: `["ts_code", "trade_date"]`

**引擎**: `ReplacingMergeTree(version)`

### 2. tushare_index_basic

**API接口**: `index_basic`

**表结构**: `dim_index_basic`（维度表）

**字段列表**:
- ts_code - TS代码
- name - 简称
- fullname - 指数全称
- market - 市场（SSE/SZSE/CSI/CICC/SW/OTH）
- publisher - 发布方
- index_type - 指数风格
- category - 指数类别
- base_date - 基期
- base_point - 基点
- list_date - 发布日期
- weight_rule - 加权方式
- desc - 描述
- exp_date - 终止日期

**调度策略**:
- 初始化时全量拉取
- 每周或每月增量更新（检查list_date变化）

### 3. tushare_index_weight

**API接口**: `index_weight`

**表结构**: `ods_index_weight`

**字段列表**:
- index_code - 指数代码
- con_code - 成分股代码
- trade_date - 交易日期
- weight - 权重
- version - 版本号
- _ingested_at - 入库时间

**分区策略**: 按月分区 `toYYYYMM(trade_date)`

**排序键**: `["index_code", "con_code", "trade_date"]`

**引擎**: `ReplacingMergeTree(version)`

**数据获取策略**:
- 每月1日更新前月数据
- 使用start_date和end_date获取月度数据

## 数据流程

```
TuShare API → Extractor → Plugin.validate_data() 
                      → Plugin.transform_data() 
                      → Plugin.load_data() 
                      → ClickHouse
```

## 关键技术决策

### 1. 数据类型转换
- 日期字段使用`Date`类型
- 数值字段使用`Nullable(Float64)`类型（TuShare可能返回NaN）
- 字符串字段使用`String`类型
- 指数代码使用`LowCardinality(String)`优化存储

### 2. 分区策略
- 按月分区，便于按时间范围查询
- 减少单次扫描数据量，提高查询性能

### 3. 版本控制
- 使用`ReplacingMergeTree`引擎
- `version`字段使用`int(datetime.now().timestamp())`
- 相同键值的数据保留最新版本

### 4. 限流策略
- idx_factor_pro: rate_limit = 30（每分钟30次）
- index_basic: rate_limit = 500
- index_weight: rate_limit = 30

### 5. 错误处理
- API调用失败重试3次（指数退避）
- 记录详细日志
- 返回空DataFrame而非抛异常

## 集成点

### Plugin Manager
- 在`plugins/__init__.py`中注册新插件
- 支持CLI命令调用：`uv run cli.py ingest-daily --plugin tushare_idx_factor_pro --date 20260110`

### Data Management
- 插件自动出现在数据管理界面
- 支持数据预览、同步任务管理

### MCP Server
- 通过service.py提供查询接口
- 支持HTTP API和MCP协议访问
