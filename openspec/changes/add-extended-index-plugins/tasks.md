# 扩展指数数据源插件开发任务清单

## Phase 1: 指数周线/月线行情插件

### 1.1 tushare_index_weekly（指数周线行情）
- [x] 1.1.1 创建插件目录结构
- [x] 1.1.2 实现 extractor.py（index_weekly API 调用）
- [x] 1.1.3 实现 plugin.py 主类
- [x] 1.1.4 创建 config.json 配置文件
- [x] 1.1.5 创建 schema.json 表结构定义
- [x] 1.1.6 创建 __init__.py 注册插件
- [x] 1.1.7 实现 service.py 查询 SDK

### 1.2 tushare_index_monthly（指数月线行情）
- [x] 1.2.1 创建插件目录结构
- [x] 1.2.2 实现 extractor.py（index_monthly API 调用）
- [x] 1.2.3 实现 plugin.py 主类
- [x] 1.2.4 创建 config.json 配置文件
- [x] 1.2.5 创建 schema.json 表结构定义
- [x] 1.2.6 创建 __init__.py 注册插件
- [x] 1.2.7 实现 service.py 查询 SDK

## Phase 2: 国际指数与大盘指标插件

### 2.1 tushare_index_global（国际指数行情）
- [x] 2.1.1 创建插件目录结构
- [x] 2.1.2 实现 extractor.py（index_global API 调用）
- [x] 2.1.3 实现 plugin.py 主类
- [x] 2.1.4 创建 config.json 配置文件
- [x] 2.1.5 创建 schema.json 表结构定义
- [x] 2.1.6 创建 __init__.py 注册插件
- [x] 2.1.7 实现 service.py 查询 SDK

### 2.2 tushare_index_dailybasic（大盘指数每日指标）
- [x] 2.2.1 创建插件目录结构
- [x] 2.2.2 实现 extractor.py（index_dailybasic API 调用）
- [x] 2.2.3 实现 plugin.py 主类
- [x] 2.2.4 创建 config.json 配置文件
- [x] 2.2.5 创建 schema.json 表结构定义
- [x] 2.2.6 创建 __init__.py 注册插件
- [x] 2.2.7 实现 service.py 查询 SDK

## Phase 3: 行业分类与成分股插件

### 3.1 tushare_index_classify（申万行业分类）
- [x] 3.1.1 创建插件目录结构
- [x] 3.1.2 实现 extractor.py（index_classify API 调用）
- [x] 3.1.3 实现 plugin.py 主类
- [x] 3.1.4 创建 config.json 配置文件
- [x] 3.1.5 创建 schema.json 表结构定义
- [x] 3.1.6 创建 __init__.py 注册插件
- [x] 3.1.7 实现 service.py 查询 SDK

### 3.2 tushare_index_member（指数成分股）
- [x] 3.2.1 创建插件目录结构
- [x] 3.2.2 实现 extractor.py（index_member API 调用）
- [x] 3.2.3 实现 plugin.py 主类
- [x] 3.2.4 创建 config.json 配置文件
- [x] 3.2.5 创建 schema.json 表结构定义
- [x] 3.2.6 创建 __init__.py 注册插件
- [x] 3.2.7 实现 service.py 查询 SDK

### 3.3 tushare_sw_daily（申万行业指数日线行情）
- [x] 3.3.1 创建插件目录结构
- [x] 3.3.2 实现 extractor.py（sw_daily API 调用）
- [x] 3.3.3 实现 plugin.py 主类
- [x] 3.3.4 创建 config.json 配置文件
- [x] 3.3.5 创建 schema.json 表结构定义
- [x] 3.3.6 创建 __init__.py 注册插件
- [x] 3.3.7 实现 service.py 查询 SDK

### 3.4 tushare_ci_daily（中信行业指数日线行情）
- [x] 3.4.1 创建插件目录结构
- [x] 3.4.2 实现 extractor.py（ci_daily API 调用）
- [x] 3.4.3 实现 plugin.py 主类
- [x] 3.4.4 创建 config.json 配置文件
- [x] 3.4.5 创建 schema.json 表结构定义
- [x] 3.4.6 创建 __init__.py 注册插件
- [x] 3.4.7 实现 service.py 查询 SDK

## Phase 4: 同花顺概念数据插件

### 4.1 tushare_ths_member（同花顺概念成分）
- [x] 4.1.1 创建插件目录结构
- [x] 4.1.2 实现 extractor.py（ths_member API 调用）
- [x] 4.1.3 实现 plugin.py 主类
- [x] 4.1.4 创建 config.json 配置文件
- [x] 4.1.5 创建 schema.json 表结构定义
- [x] 4.1.6 创建 __init__.py 注册插件
- [x] 4.1.7 实现 service.py 查询 SDK

## Phase 5: 市场统计数据插件

### 5.1 tushare_sz_daily_info（深圳市场每日交易概况）
- [x] 5.1.1 创建插件目录结构
- [x] 5.1.2 实现 extractor.py（sz_daily_info API 调用）
- [x] 5.1.3 实现 plugin.py 主类
- [x] 5.1.4 创建 config.json 配置文件
- [x] 5.1.5 创建 schema.json 表结构定义
- [x] 5.1.6 创建 __init__.py 注册插件
- [x] 5.1.7 实现 service.py 查询 SDK

### 5.2 tushare_daily_info（每日全市场交易统计）
- [x] 5.2.1 创建插件目录结构
- [x] 5.2.2 实现 extractor.py（daily_info API 调用）
- [x] 5.2.3 实现 plugin.py 主类
- [x] 5.2.4 创建 config.json 配置文件
- [x] 5.2.5 创建 schema.json 表结构定义
- [x] 5.2.6 创建 __init__.py 注册插件
- [x] 5.2.7 实现 service.py 查询 SDK

## Phase 6: 估值与其他数据插件

### 6.1 tushare_index_e（中证指数估值）
- [x] 6.1.1 创建插件目录结构
- [x] 6.1.2 实现 extractor.py（index_e/index_value API 调用）
- [x] 6.1.3 实现 plugin.py 主类
- [x] 6.1.4 创建 config.json 配置文件
- [x] 6.1.5 创建 schema.json 表结构定义
- [x] 6.1.6 创建 __init__.py 注册插件
- [x] 6.1.7 实现 service.py 查询 SDK

### 6.2 tushare_stk_rewards（管理层薪酬和持股）
- [x] 6.2.1 创建插件目录结构
- [x] 6.2.2 实现 extractor.py（stk_rewards API 调用）
- [x] 6.2.3 实现 plugin.py 主类
- [x] 6.2.4 创建 config.json 配置文件
- [x] 6.2.5 创建 schema.json 表结构定义
- [x] 6.2.6 创建 __init__.py 注册插件
- [x] 6.2.7 实现 service.py 查询 SDK

## Phase 7: 集成与验证

### 7.1 数据库初始化
- [ ] 7.1.1 执行 `uv run cli.py init-db` 创建所有新表结构

### 7.2 CLI 命令测试
- [ ] 7.2.1 测试 index_weekly 数据获取
- [ ] 7.2.2 测试 index_monthly 数据获取
- [ ] 7.2.3 测试 index_global 数据获取
- [ ] 7.2.4 测试 index_dailybasic 数据获取
- [ ] 7.2.5 测试 index_classify 数据获取
- [ ] 7.2.6 测试 index_member 数据获取
- [ ] 7.2.7 测试 sw_daily 数据获取
- [ ] 7.2.8 测试 ci_daily 数据获取
- [ ] 7.2.9 测试 ths_member 数据获取
- [ ] 7.2.10 测试 sz_daily_info 数据获取
- [ ] 7.2.11 测试 daily_info 数据获取
- [ ] 7.2.12 测试 index_e 数据获取
- [ ] 7.2.13 测试 stk_rewards 数据获取

### 7.3 数据验证
- [ ] 7.3.1 验证数据完整性（查询 ClickHouse）
- [ ] 7.3.2 验证数据管理界面显示
- [ ] 7.3.3 验证 MCP 接口可用性

### 7.4 文档更新
- [ ] 7.4.1 更新 README.md 文档

## 注意事项

### TUSHARE_TOKEN 配置
- 所有 TuShare 插件需要配置环境变量 `TUSHARE_TOKEN`
- 如果未配置，插件加载会失败，数据库表结构创建也会失败
- 配置方法：在 `.env` 文件中添加 `TUSHARE_TOKEN=your_token`

### 积分要求
不同接口需要不同积分额度：
- 基础接口（index_weekly、index_monthly）：600积分
- 高级接口（index_global、sw_daily、ci_daily、index_classify、stk_rewards）：2000积分
- index_dailybasic：400积分

### 测试步骤
1. 配置 TUSHARE_TOKEN 环境变量
2. 运行 `uv run cli.py init-db` 创建表结构
3. 运行各个插件的 ingest 命令测试数据获取
4. 验证数据是否正确写入数据库
5. 通过 MCP 接口测试查询功能

### 插件实现顺序建议
建议按以下顺序实现，以便验证依赖关系：
1. index_classify（行业分类基础数据）
2. index_member（成分股依赖分类数据）
3. sw_daily / ci_daily（行业行情依赖分类数据）
4. 其他独立插件可并行开发
