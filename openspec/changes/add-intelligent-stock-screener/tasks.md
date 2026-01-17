# Tasks: M03智能选股模块实现任务

## 数据访问原则

**重要**：所有数据获取应优先调用 `plugins/` 目录下的 Service 接口，避免直接写 SQL 查询。

可用的 Plugin Services：
- `TuShareDailyBasicService` - PE/PB/换手率等估值指标
- `TuShareStockBasicService` - 股票基本信息/行业/上市状态
- `TuShareDailyService` - 日线行情数据
- `TuShareFinaceIndicatorService` - 财务指标数据
- `TuShareAdjFactorService` - 复权因子

## 1. 后端基础设施

- [x] 1.1 创建 `src/stock_datasource/modules/screener/schemas.py` 定义数据模型
  - ScreenerCondition, ScreenerRequest, StockProfile, Recommendation 等
- [x] 1.2 创建 `src/stock_datasource/modules/screener/service.py` 选股服务
  - **优先使用 Plugin Services 获取数据**
  - 注入 TuShareDailyBasicService, TuShareStockBasicService, TuShareDailyService 等
  - filter_by_conditions() 多条件筛选（调用 plugin service 获取原始数据）
  - get_available_fields() 获取可筛选字段
  - get_sectors() 获取行业列表（调用 TuShareStockBasicService）
- [x] 1.3 增强 `router.py` 添加新API端点
  - GET /fields 增强（添加技术指标字段）
  - GET /sectors 行业列表
  - GET /sectors/{sector}/stocks 行业内选股

## 2. 十维画像功能

- [x] 2.1 创建 `src/stock_datasource/modules/screener/profile.py` 画像计算
  - **优先调用 Plugin Services 获取原始数据**
  - 使用 TuShareDailyBasicService 获取估值数据
  - 使用 TuShareDailyService 获取行情数据
  - 使用 TuShareFinaceIndicatorService 获取财务数据
  - calculate_valuation_score() 估值维度
  - calculate_momentum_score() 动量维度
  - calculate_trend_score() 趋势维度
  - calculate_volume_score() 量能维度
  - calculate_total_profile() 综合画像
- [x] 2.2 添加画像API端点
  - GET /profile/{ts_code} 单股画像
  - POST /batch-profile 批量画像

## 3. 自然语言选股增强

- [x] 3.1 增强 `screener_agent.py` 的NL解析能力
  - 优化system prompt
  - 添加条件解析工具
  - 添加结果验证逻辑
- [x] 3.2 增强 `tools.py` 添加选股工具函数
  - screen_by_nl() 自然语言选股
  - validate_conditions() 条件验证
- [x] 3.3 优化 `/nl` 端点返回解析结果

## 4. AI推荐功能

- [x] 4.1 添加推荐服务
  - get_daily_recommendations() 每日推荐
  - get_hot_stocks() 热门股票
  - get_technical_signals() 技术信号股
- [x] 4.2 添加推荐API端点
  - GET /recommendations 获取推荐
  - GET /signals 技术信号

## 5. 前端组件开发

- [x] 5.1 增强 `ConditionBuilder.vue` 
  - 添加更多筛选字段
  - 添加行业选择器
  - 添加技术指标条件
- [x] 5.2 创建 `ProfileCard.vue` 股票画像卡片
  - 显示十维评分
  - 雷达图可视化
- [x] 5.3 创建 `NLScreener.vue` 自然语言选股组件
  - 输入框 + 示例提示
  - 解析结果展示
- [x] 5.4 创建 `RecommendationPanel.vue` 推荐面板
  - 每日推荐列表
  - 推荐理由展示

## 6. 前端状态管理

- [x] 6.1 增强 `screener.ts` store
  - 添加画像数据状态
  - 添加推荐数据状态
  - 添加行业筛选状态
- [x] 6.2 增强 `screener.ts` API
  - 添加画像API调用
  - 添加推荐API调用

## 7. 集成与测试

- [x] 7.1 增强 `ScreenerView.vue` 集成新组件
  - 添加画像展示入口
  - 添加推荐面板
  - 优化布局
- [x] 7.2 编写后端单元测试
  - 筛选服务测试
  - 画像计算测试
- [x] 7.3 端到端测试
  - 条件筛选流程
  - NL选股流程
  - 画像查看流程

## Dependencies

- Task 1.x 是其他任务的基础，需优先完成
- Task 2.x 依赖 Task 1.x
- Task 3.x 依赖 Task 1.x
- Task 4.x 依赖 Task 2.x（推荐需要画像数据）
- Task 5.x 和 6.x 可与后端并行开发（使用Mock数据）
- Task 7.x 需要所有功能完成后进行

## Parallelizable Work

- Task 1.x 和 Task 5.x/6.x 可并行（前后端分离开发）
- Task 2.x 和 Task 3.x 可并行
- Task 5.1-5.4 各组件可并行开发
