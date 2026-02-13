# Design: migrate-hk-daily-to-finnhub

## Context

港股日线数据是股票分析的重要基础数据。当前系统使用 TuShare API 获取港股日线数据,但由于权限限制,无法获取完整的历史数据。需要迁移到数据完整且稳定的数据源。

### 数据源选择决策

经过对比分析,选择 Finnhub 作为数据源:

| 数据源 | 优点 | 缺点 | 选择 |
|--------|------|------|------|
| TuShare | 项目已集成 | 权限不足,无法获取完整数据 | ❌ |
| yfinance | 免费 | 速率限制严重,经常无法使用 | ❌ |
| akshare | 免费 | 存在IP限制问题 | ❌ |
| **Finnhub** | API稳定,数据完整,速率限制明确(60次/min) | 需要API Key | ✅ |

### 约束条件
- 必须保持数据库表结构不变,确保向后兼容
- 必须保持查询 API 接口不变,前端无需修改
- 必须支持批量获取所有港股的历史数据
- 必须实现数据格式映射,确保数据一致性
- 必须使用 uv 管理项目依赖,不使用 pip
- 必须从 tushare_hk_basic 插件获取股票列表

### 相关方
- 数据工程师: 负责数据迁移实现
- 前端开发者: 使用查询 API 的消费者(无需修改)
- 运维人员: 部署和监控数据采集任务

## Goals / Non-Goals

### Goals
1. 使用 Finnhub 获取港股日线数据,解决权限问题
2. 实现数据格式映射,保持与 TuShare 格式兼容
3. 创建独立脚本批量获取所有港股最近一年的历史数据
4. 保持数据库表结构和查询接口不变
5. 使用 uv 管理依赖

### Non-Goals
1. 不修改数据库表结构或添加新字段
2. 不修改前端代码或查询服务
3. 不提供成交额(amount)数据(Finnhub 不支持)
4. 不处理实时数据(Finnhub 有延迟,适合历史数据)
5. 不修改现有插件架构,通过独立脚本实现

## Decisions

### 1. 数据源选择

**决策**: 使用 Finnhub 替代 TuShare

**理由**:
- ✅ 提供免费 API 套餐,足够个人使用
- ✅ 数据完整,覆盖所有港股
- ✅ API 稳定可靠,数据质量好
- ✅ 速率限制明确: 60 次/分钟,可控
- ❌ 缺少成交额字段(可接受)
- ❌ 需要申请 API Key(免费申请)

**API Key 获取**:
- 访问 https://finnhub.io/register
- 免费注册获取 API Key
- 免费套餐限制: 60 次/分钟

**备选方案**:
- yfinance: 速率限制严重,无法稳定使用
- akshare: 存在IP限制问题

### 2. 代码格式转换

**决策**: 实现双向转换函数

**方案**:
```python
# TuShare 格式: 00700.HK (5位数字)
# Finnhub 格式: 0700.HK (4位数字)

def ts_code_to_finnhub(ts_code: str) -> str:
    """TuShare code to Finnhub symbol"""
    # 00700.HK -> 0700.HK
    code, suffix = ts_code.split('.')
    code = code.lstrip('0') or '0'  # Remove leading zeros, but keep at least one digit
    return f"{code}.{suffix}"

def finnhub_to_ts_code(symbol: str) -> str:
    """Finnhub symbol to TuShare code"""
    # 0700.HK -> 00700.HK
    code, suffix = symbol.split('.')
    code = code.zfill(5)  # Pad to 5 digits
    return f"{code}.{suffix}"
```

**理由**: 保持数据库中使用 TuShare 格式,仅在数据获取时转换

### 3. 数据字段映射

**决策**: 在脚本中实现字段映射和计算

**映射表**:
| TuShare 字段 | Finnhub 字段 | 说明 |
|------------|-------------|------|
| ts_code | symbol | 从参数获取,使用 TuShare 格式 |
| trade_date | t (timestamp) | 从时间戳转换为 YYYYMMDD 格式 |
| open | o | 直接映射 |
| high | h | 直接映射 |
| low | l | 直接映射 |
| close | c | 直接映射 |
| vol | v | 直接映射 |
| pre_close | c (t-1) | 从前一天的 close 计算 |
| change | c - pre_close | 计算涨跌额 |
| pct_chg | (c - pre_close) / pre_close * 100 | 计算涨跌幅 |
| amount | N/A | 设为 null |

**Finnhub API 响应示例**:
```json
{
  "c": [148.5, 149.2, ...],  // close prices
  "h": [149.5, 150.0, ...],  // high prices
  "l": [148.0, 148.5, ...],  // low prices
  "o": [148.5, 149.0, ...],  // open prices
  "s": "ok",                  // status
  "t": [1605542400, 1605628800, ...],  // timestamps
  "v": [123456, 234567, ...]  // volumes
}
```

**理由**: 保持数据库格式统一,前端和查询服务无需修改

### 4. 批量获取策略

**决策**: 创建独立脚本实现批量获取

**方案**:
```python
# scripts/fetch_hk_daily_from_finnhub.py

def fetch_all_hk_stocks():
    """获取所有港股的历史数据"""
    # 1. 从数据库 ods_hk_basic 表获取股票列表
    # 2. 严格按照 60 次/分钟的速率控制
    # 3. 获取最近一年的数据
    # 4. 错误处理和重试机制
    # 5. 记录进度和统计信息
    # 6. 直接写入数据库
```

**参数**:
- 时间范围: 最近一年 (start_date 到 end_date)
- 速率限制: 60 次/分钟 (Finnhub 免费套餐限制)
- 数据源: ods_hk_basic 表 (已由 tushare_hk_basic 插件维护)

**理由**: 
- 不修改现有插件架构
- 通过独立脚本实现,易于维护和调试
- 速率控制清晰明确
- 支持断点续传和错误恢复

### 5. 速率控制

**决策**: 实现精确的速率控制

**方案**:
```python
class FinnhubRateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute  # 1秒
        self.last_call_time = 0
    
    def acquire(self):
        """等待直到可以进行下一次调用"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
```

**配置**:
- 速率: 60 次/分钟 = 1 次/秒
- 脚本中硬编码,不从配置文件读取

**理由**: 
- Finnhub 免费套餐限制明确,无需令牌桶等复杂算法
- 简单的时间间隔控制即可满足需求
- 避免触发 Finnhub API 限制

## Risks / Trade-offs

### Risk 1: yfinance API 不稳定
- **风险**: Yahoo Finance 可能更新 API 或增加限制
- **缓解**: 
  - 实现重试机制
  - 记录获取进度,支持断点续传
  - 监控获取失败率,及时报警

### Risk 2: 数据缺失字段
- **风险**: yfinance 不提供成交额(amount)字段
- **影响**: 部分分析功能可能受影响
- **缓解**: 
  - 在文档中明确说明字段缺失
  - amount 字段设为 null,不影响其他字段使用
  - 未来可考虑从其他数据源补充

### Risk 3: 历史数据不一致
- **风险**: yfinance 和 TuShare 的历史数据可能有差异
- **影响**: 切换数据源后,历史数据可能出现跳变
- **缓解**: 
  - 提供数据源标记字段(可选)
  - 重新获取完整历史数据,避免混合数据源
  - 文档说明数据源切换

### Risk 4: 股票代码格式转换错误
- **风险**: 代码格式转换可能出错
- **影响**: 无法获取正确的股票数据
- **缓解**: 
  - 充分测试转换逻辑
  - 实现格式验证
  - 记录转换日志

## Migration Plan

### Phase 1: 开发和测试(1-2 天)
1. 实现 yfinance extractor
2. 实现字段映射和计算逻辑
3. 实现批量获取和速率控制
4. 单元测试和集成测试

### Phase 2: 小规模验证(0.5 天)
1. 选择 10-20 只港股进行测试
2. 验证数据格式正确性
3. 验证查询服务功能正常
4. 对比 TuShare 数据(如有)

### Phase 3: 全量获取(1-2 天)
1. 获取所有港股的历史数据(至少一年)
2. 监控获取进度和错误率
3. 处理失败的数据(重试或跳过)
4. 验证数据完整性

### Phase 4: 切换上线(0.5 天)
1. 更新配置文件
2. 重启数据采集服务
3. 监控数据质量
4. 文档更新

### 回滚计划
如果迁移后发现问题:
1. 恢复原 TuShare extractor 代码
2. 重启服务
3. 数据库数据无需回滚(格式兼容)

## Open Questions

1. **是否需要保留 TuShare 作为备用数据源?**
   - 建议: 可以保留代码,通过配置切换数据源
   - 实现: 在 config.json 中添加 `data_source` 字段

2. **是否需要实现增量更新?**
   - 建议: 是,每天增量更新最新数据
   - 实现: 根据最新交易日期获取增量数据

3. **如何处理停牌股票?**
   - 建议: yfinance 会返回空数据或历史最后数据
   - 实现: 记录警告日志,不影响其他股票

4. **是否需要实现数据质量监控?**
   - 建议: 是,监控数据完整性和异常值
   - 实现: 添加数据验证和报警机制
