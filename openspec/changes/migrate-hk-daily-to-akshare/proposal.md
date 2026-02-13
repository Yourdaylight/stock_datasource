# Proposal: migrate-hk-daily-to-akshare

## Why

当前港股日线数据插件 `tushare_hk_daily` 使用 TuShare API 获取数据,但存在以下问题:
1. **权限限制**: TuShare 港股日线数据需要高级权限,普通用户无法获取完整历史数据
2. **数据缺失**: 由于权限不足,无法获取所有港股的历史日线数据
3. **依赖外部服务**: 强依赖 TuShare 服务,受其可用性限制

使用 AKShare 作为替代方案的优势:
- **完全免费**: AKShare 是开源免费的,无需权限限制
- **数据完整**: 可获取所有港股的完整历史数据(测试显示可获取20+年数据)
- **已集成**: 项目中已安装并使用 AKShare
- **数据稳定**: 成功测试获取腾讯(00700)5327条历史数据

**数据源选择决策过程**:
- ❌ TuShare: 权限不足,无法获取完整数据
- ❌ yfinance: 速率限制严重,经常触发限制无法使用
- ❌ Finnhub: 免费套餐不支持港股历史数据(403错误)
- ✅ **AKShare**: 免费、无速率限制、数据完整、已集成

## What Changes

将港股日线数据插件从 TuShare 迁移到 AKShare,保持数据格式兼容:

1. **数据源迁移**: 从 TuShare `hk_daily` API 迁移到 AKShare `stock_hk_daily`
2. **字段映射**: 将 AKShare 数据格式映射到 TuShare 格式,保持数据库表结构不变
3. **代码转换**: 实现 TuShare 代码格式(00700.HK)到 AKShare 格式(00700)的转换
4. **批量获取**: 创建独立脚本批量获取所有港股最近一年的历史数据
5. **依赖管理**: 使用 uv 管理项目依赖,不使用 pip

**关键映射关系**:
- AKShare 字段: `date, open, high, low, close, volume`
- TuShare 字段: `trade_date, open, high, low, close, vol`
- 代码转换: 00700.HK → 00700 (去掉后缀)
- 计算字段: `pre_close`, `change`, `pct_chg` (从历史数据计算)
- 缺失字段: `amount` (AKShare 无此字段,设为 null)

## Impact

### 受影响的规范
- **hk-daily-data** (新建): 定义港股日线数据获取和存储规范

### 受影响的代码
- `src/stock_datasource/plugins/tushare_hk_daily/extractor.py` - 重写为使用 AKShare
- `src/stock_datasource/plugins/tushare_hk_daily/plugin.py` - 更新插件逻辑
- `src/stock_datasource/plugins/tushare_hk_daily/config.json` - 更新配置(移除 TuShare token 依赖)
- `pyproject.toml` - 已有 akshare 依赖
- `scripts/fetch_hk_daily_from_akshare.py` - 新增批量获取脚本

### 数据兼容性
- ✅ **数据库表结构保持不变** - ods_hk_daily 表结构无需修改
- ✅ **API 接口保持兼容** - 前端和查询服务无需修改
- ✅ **数据格式保持一致** - 使用相同的字段名和数据类型

### 迁移风险
1. **字段缺失**: Finnhub 不提供成交额(amount)字段,该字段将设为 null
2. **API 限制**: Finnhub 免费套餐限制 60 次/分钟,需要合理的速率控制
3. **API Key**: 需要 Finnhub API Key (免费申请)
4. **历史数据**: 需要重新获取历史数据以替换原有 TuShare 数据

### 实施策略
1. **独立脚本**: 创建独立的批量获取脚本,不修改现有插件代码
2. **速率控制**: 严格按照 60 次/分钟控制请求速率
3. **数据源**: 从 `tushare_hk_basic` 插件获取港股股票列表
4. **时间范围**: 获取最近一年的历史日线数据
5. **依赖管理**: 使用 `uv add finnhub-python` 添加依赖

### 测试验证
- 必须测试获取港股所有股票至少一年的历史日线数据
- 验证数据格式与原有 TuShare 数据一致
- 验证查询服务功能正常
