# ETF插件开发任务清单

## Phase 1: tushare_idx_factor_pro

- [x] 创建插件目录结构
- [x] 实现extractor.py（idx_factor_pro API调用）
- [x] 实现plugin.py主类
  - [x] extract_data方法
  - [x] validate_data方法
  - [x] transform_data方法
  - [x] load_data方法
- [x] 创建config.json配置文件
- [x] 创建schema.json表结构定义（100+字段）
- [x] 创建__init__.py注册插件
- [x] 实现service.py查询SDK
- [ ] 单元测试（mock API调用）
- [ ] 集成测试（真实API调用）

## Phase 2: tushare_index_basic

- [x] 创建插件目录结构
- [x] 实现extractor.py（index_basic API调用）
- [x] 实现plugin.py主类
  - [x] extract_data方法
  - [x] validate_data方法
  - [x] transform_data方法
  - [x] load_data方法
- [x] 创建config.json配置文件
- [x] 创建schema.json表结构定义
- [x] 创建__init__.py注册插件
- [x] 实现service.py查询SDK
- [ ] 单元测试（mock API调用）
- [ ] 集成测试（真实API调用）

## Phase 3: tushare_index_weight

- [x] 创建插件目录结构
- [x] 实现extractor.py（index_weight API调用）
- [x] 实现plugin.py主类
  - [x] extract_data方法
  - [x] validate_data方法
  - [x] transform_data方法
  - [x] load_data方法
- [x] 创建config.json配置文件
- [x] 创建schema.json表结构定义
- [x] 创建__init__.py注册插件
- [x] 实现service.py查询SDK
- [ ] 单元测试（mock API调用）
- [ ] 集成测试（真实API调用）

## Phase 4: 集成与验证

- [x] 更新plugins/__init__.py注册所有新插件（插件自动发现，无需手动注册）
- [ ] 执行`uv run cli.py init-db`创建表结构（需要配置TUSHARE_TOKEN）
- [ ] 测试CLI命令调用
  - [ ] `uv run cli.py ingest-daily --plugin tushare_idx_factor_pro --date 20260110`
  - [ ] `uv run cli.py ingest-daily --plugin tushare_index_basic`
  - [ ] `uv run cli.py ingest-daily --plugin tushare_index_weight --date 20260101`
- [ ] 验证数据完整性（查询ClickHouse）
- [ ] 验证数据管理界面显示
- [ ] 验证MCP接口可用性
- [ ] 性能测试（批量数据加载）
- [ ] 文档更新（README.md）

## 注意事项

**TUSHARE_TOKEN配置**:
- 所有TuShare插件需要配置环境变量`TUSHARE_TOKEN`
- 如果未配置，插件加载会失败，数据库表结构创建也会失败
- 配置方法：在.env文件中添加`TUSHARE_TOKEN=your_token`

**测试步骤**:
1. 配置TUSHARE_TOKEN环境变量
2. 运行`uv run cli.py init-db`创建表结构
3. 运行各个插件的ingest命令测试数据获取
4. 验证数据是否正确写入数据库
5. 通过MCP接口测试查询功能
