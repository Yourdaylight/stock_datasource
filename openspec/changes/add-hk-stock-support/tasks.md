# Tasks: add-hk-stock-support

## Phase 1: 后端扩展 (Backend)

- [x] 1.1 扩展 Market Service 支持港股代码识别
  - 识别 `.HK` 后缀的股票代码
  - 路由到 `tushare_hk_daily` 数据源

- [x] 1.2 添加港股 K 线查询接口
  - 复用现有 `/api/market/kline` 接口
  - 内部根据代码后缀选择数据源

- [x] 1.3 添加港股复权支持
  - 集成 `tushare_hk_adjfactor` 进行前复权/后复权计算

- [x] 1.4 添加港股股票名称查询
  - 通过 `tushare_hk_basic` 获取股票名称

## Phase 2: 前端股票详情适配 (Stock Detail)

- [x] 2.1 检测股票市场类型
  - 根据代码后缀判断 A 股/港股

- [x] 2.2 港股详情页面适配
  - 隐藏不支持的功能（筹码峰、十维画像）
  - 保留 K 线图、AI 分析等通用功能

- [x] 2.3 港股行情显示适配
  - 移除涨跌停相关标记
  - 显示港币符号（HKD）

## Phase 3: 股票列表支持港股 (Stock List)

- [x] 3.1 添加市场类型筛选
  - 支持切换 A 股/港股/全部

- [x] 3.2 港股列表展示
  - 调用 `tushare_hk_basic` 获取港股列表
  - 关联 `tushare_hk_daily` 获取最新行情

- [x] 3.3 统一股票搜索
  - 支持同时搜索 A 股和港股

## Validation

- [ ] V1: 验证港股 K 线数据加载正常
- [ ] V2: 验证港股详情页面功能完整
- [ ] V3: 验证股票列表切换市场类型正常
