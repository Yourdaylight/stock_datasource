# Change: 升级新闻板块 - 接入 Tushare 6 大新闻类 API

## Why

当前新闻板块仅接入了 Tushare 公告（`anns()`）和新浪财经两个数据源，数据类型单一，缺少快讯、长篇通讯、新闻联播、券商研报、国家政策等重要信息维度。用户已获取 Tushare 6 个新闻类接口权限，需要将这些数据源全部整合到资讯中心，提供更全面的财经信息服务。

## What Changes

### 后端 - 新增 6 个 Tushare 数据源接入
- **`news`**（新闻快讯）：9 大财经媒体短讯（新浪/华尔街见闻/同花顺/东方财富/云财经/凤凰/金融界/财联社/第一财经），作为主数据源
- **`major_news`**（新闻通讯）：长篇深度新闻（新华网/凤凰财经/同花顺/新浪财经/华尔街见闻/中证网/财新网/第一财经/财联社）
- **`cctv_news`**（新闻联播）：新闻联播文字稿，2017 年至今
- **`anns_d`**（上市公司公告）：替代现有 `anns()` 接口，支持更完善的日期查询
- **`research_report`**（券商研报）：个股/行业研报数据，2017 年至今
- **`npr`**（国家政策库）：国家行政机关法规、政策、批复、通知等

### 后端 - NewsService 重构
- 统一数据源管理器，采用**按源分组并发 + 组内串行限频**拉取策略
- 新增 `NewsSource` 枚举扩展（tushare_news / tushare_major / tushare_cctv / tushare_anns / tushare_report / tushare_npr）
- `NewsCategory` 扩展：新增 `RESEARCH`（研报）、`CCTV`（新闻联播）、`NPR`（国家政策）分类
- 各数据源独立的缓存策略和更新频率
- 支持部分数据源失败时的降级返回（不因单源失败中断整体响应）
- 新浪数据源调整为兜底能力（可配置开关），稳定后可下线

### 前端 - 资讯中心 UI 升级
- 新增 Tab：**新闻联播**、**政策法规**
- **新闻快讯** Tab 升级：来源筛选支持 9 大媒体源
- **研报数据** Tab 升级：接入 `research_report` API 替代/增强现有数据
- 新闻分类筛选器扩展
- 公告数据切换为 `anns_d` 接口（支持日期范围查询）
- 政策正文 HTML 渲染增加安全净化（XSS 防护）

## Impact
- Affected specs: news-datasources (新增), news-frontend (修改)
- Affected code:
  - `src/stock_datasource/modules/news/service.py` — 核心数据拉取逻辑重构
  - `src/stock_datasource/modules/news/schemas.py` — 数据模型扩展
  - `src/stock_datasource/modules/news/router.py` — 新增/修改 API 端点
  - `frontend/src/views/news/` — UI 组件升级
  - `frontend/src/stores/news.ts` — 状态管理扩展
  - `frontend/src/api/news.ts` — API 接口层扩展
  - `frontend/src/types/news.ts` — TypeScript 类型扩展
