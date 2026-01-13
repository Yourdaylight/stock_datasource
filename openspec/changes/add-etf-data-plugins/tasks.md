# ETF数据插件开发任务清单

## Phase 1: tushare_etf_basic（基础信息 - 优先实现）

- [x] 1.1 创建config.json配置文件
- [x] 1.2 创建schema.json表结构定义
- [x] 1.3 实现extractor.py（etf_basic API调用）
- [x] 1.4 实现plugin.py主类
  - [x] extract_data方法
  - [x] validate_data方法
  - [x] transform_data方法
  - [x] load_data方法
- [x] 1.5 创建__init__.py注册插件
- [x] 1.6 实现service.py查询SDK

## Phase 2: tushare_etf_fund_daily（日线行情）

- [x] 2.1 创建config.json配置文件
- [x] 2.2 创建schema.json表结构定义
- [x] 2.3 实现extractor.py（fund_daily API调用）
- [x] 2.4 实现plugin.py主类（声明依赖tushare_etf_basic）
- [x] 2.5 创建__init__.py注册插件
- [x] 2.6 实现service.py查询SDK

## Phase 3: tushare_etf_fund_adj（复权因子）

- [x] 3.1 创建config.json配置文件
- [x] 3.2 创建schema.json表结构定义
- [x] 3.3 实现extractor.py（fund_adj API调用）
- [x] 3.4 实现plugin.py主类（声明依赖tushare_etf_basic）
- [x] 3.5 创建__init__.py注册插件
- [x] 3.6 实现service.py查询SDK

## Phase 4: tushare_etf_stk_mins（分钟数据）

- [x] 4.1 创建config.json配置文件
- [x] 4.2 创建schema.json表结构定义
- [x] 4.3 实现extractor.py（stk_mins API调用）
- [x] 4.4 实现plugin.py主类（声明依赖tushare_etf_basic）
- [x] 4.5 创建__init__.py注册插件
- [x] 4.6 实现service.py查询SDK

## Phase 5: 测试与验证

- [x] 5.1 创建tests/test_etf_plugins.py测试文件
- [x] 5.2 测试tushare_etf_basic插件
- [x] 5.3 测试tushare_etf_fund_daily插件
- [x] 5.4 测试tushare_etf_fund_adj插件
- [x] 5.5 测试tushare_etf_stk_mins插件
- [x] 5.6 验证依赖关系逻辑

## 注意事项

**依赖关系处理**:
- 日线/分钟线数据获取前需要确保有ETF基础信息
- 在plugin.py中通过`get_dependencies()`声明依赖
- 在extract_data中可以查询数据库获取ETF代码列表

**测试配置**:
- 使用runtime_config.json中的配置
- 需要配置TUSHARE_TOKEN环境变量

**API限流**:
- etf_basic: 单次最大5000条
- fund_daily: 单次最大2000条，rate_limit=30
- stk_mins: 单次最大8000条

## 测试结果

所有22个测试用例通过：
```
tests/test_etf_plugins.py::TestETFBasicPlugin::test_plugin_creation PASSED
tests/test_etf_plugins.py::TestETFBasicPlugin::test_plugin_config PASSED
tests/test_etf_plugins.py::TestETFBasicPlugin::test_plugin_schema PASSED
tests/test_etf_plugins.py::TestETFBasicPlugin::test_plugin_dependencies PASSED
tests/test_etf_plugins.py::TestETFBasicPlugin::test_extract_data PASSED
tests/test_etf_plugins.py::TestETFFundDailyPlugin::test_plugin_creation PASSED
tests/test_etf_plugins.py::TestETFFundDailyPlugin::test_plugin_dependencies PASSED
tests/test_etf_plugins.py::TestETFFundDailyPlugin::test_plugin_schema PASSED
tests/test_etf_plugins.py::TestETFFundDailyPlugin::test_extract_data PASSED
tests/test_etf_plugins.py::TestETFFundAdjPlugin::test_plugin_creation PASSED
tests/test_etf_plugins.py::TestETFFundAdjPlugin::test_plugin_dependencies PASSED
tests/test_etf_plugins.py::TestETFFundAdjPlugin::test_plugin_schema PASSED
tests/test_etf_plugins.py::TestETFFundAdjPlugin::test_extract_data PASSED
tests/test_etf_plugins.py::TestETFStkMinsPlugin::test_plugin_creation PASSED
tests/test_etf_plugins.py::TestETFStkMinsPlugin::test_plugin_dependencies PASSED
tests/test_etf_plugins.py::TestETFStkMinsPlugin::test_plugin_schema PASSED
tests/test_etf_plugins.py::TestETFStkMinsPlugin::test_extract_data PASSED
tests/test_etf_plugins.py::TestPluginDependencies::test_etf_basic_no_dependencies PASSED
tests/test_etf_plugins.py::TestPluginDependencies::test_fund_daily_depends_on_basic PASSED
tests/test_etf_plugins.py::TestPluginDependencies::test_fund_adj_depends_on_basic PASSED
tests/test_etf_plugins.py::TestPluginDependencies::test_stk_mins_depends_on_basic PASSED
tests/test_etf_plugins.py::TestPluginDiscovery::test_plugins_discoverable PASSED

============================== 22 passed in 6.46s ==============================
```
