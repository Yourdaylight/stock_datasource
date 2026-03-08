## 1. 后端 - 数据模型扩展
- [ ] 1.1 扩展 `NewsCategory` 枚举：新增 CCTV / RESEARCH / NPR 三个分类
- [ ] 1.2 扩展 `NewsItem` 模型：新增 `author`、`news_src`（新闻源标识）、`abstract`（摘要）字段
- [ ] 1.3 新增 `ResearchReport` 模型：trade_date / title / abstract / author / ts_code / inst_csname / ind_name / url
- [ ] 1.4 新增 `PolicyItem` 模型：pubtime / title / content_html / pcode / puborg / ptype / url
- [ ] 1.5 扩展列表响应模型：新增 `partial`、`failed_sources` 字段

## 2. 后端 - 6 个 Tushare 数据源接入
- [ ] 2.1 实现 `_fetch_tushare_news()` — 新闻快讯（`news` API，支持 9 大来源 src 参数）
- [ ] 2.2 实现 `_fetch_tushare_major_news()` — 新闻通讯（`major_news` API）
- [ ] 2.3 实现 `_fetch_tushare_cctv_news()` — 新闻联播（`cctv_news` API）
- [ ] 2.4 实现 `_fetch_tushare_anns_d()` — 上市公司公告（`anns_d` API，替代现有 anns）
- [ ] 2.5 实现 `_fetch_tushare_research_report()` — 券商研报（`research_report` API）
- [ ] 2.6 实现 `_fetch_tushare_npr()` — 国家政策库（`npr` API）

## 3. 后端 - Service 层整合
- [ ] 3.1 重构 `get_market_news()` 方法，按 category 路由到不同数据源
- [ ] 3.2 新增 `get_cctv_news(date)` 方法
- [ ] 3.3 新增 `get_research_reports(start_date, end_date, ts_code, report_type)` 方法
- [ ] 3.4 新增 `get_policy_news(start_date, end_date, org, ptype)` 方法
- [ ] 3.5 各数据源独立缓存策略实现
- [ ] 3.6 API 限频与并发策略（组间并发 + 组内串行 + Semaphore + 退避重试）
- [ ] 3.7 实现部分源失败降级：输出 `partial` 与 `failed_sources`
- [ ] 3.8 新增新浪兜底开关配置（默认开启）

## 4. 后端 - Router 层新增端点
- [ ] 4.1 新增 `GET /api/news/cctv` — 获取新闻联播文字稿
- [ ] 4.2 新增 `GET /api/news/policy` — 获取国家政策法规
- [ ] 4.3 修改 `GET /api/news/sources` — 返回扩展后的来源列表
- [ ] 4.4 修改 `GET /api/news/categories` — 返回扩展后的分类列表
- [ ] 4.5 修改 `GET /api/news/list` — 支持新分类和来源筛选

## 5. 前端 - 类型和 API 层扩展
- [ ] 5.1 扩展 `types/news.ts`：新增 CCTV / RESEARCH / NPR 分类，新增字段类型
- [ ] 5.2 扩展 `api/news.ts`：新增 `getCCTVNews`、`getPolicyNews` API 函数
- [ ] 5.3 扩展 `stores/news.ts`：新增 cctvNews / policyNews 状态和 actions
- [ ] 5.4 支持响应级降级字段：`partial`、`failed_sources`

## 6. 前端 - 资讯中心 UI 升级
- [ ] 6.1 NewsView.vue 新增 **新闻联播** Tab
- [ ] 6.2 NewsView.vue 新增 **政策法规** Tab
- [ ] 6.3 新建 `CCTVNewsPanel.vue` 组件 — 新闻联播面板（日期选择 + 文字稿列表）
- [ ] 6.4 新建 `PolicyNewsPanel.vue` 组件 — 政策法规面板（机构/主题筛选 + 政策列表）
- [ ] 6.5 升级 `NewsListPanel.vue` — 来源筛选器支持 9 大媒体源
- [ ] 6.6 升级研报数据 Tab — 接入 `research_report` API 增强数据
- [ ] 6.7 增加部分失败提示 UI（可用数据 + 失败来源提醒）

## 7. 安全加固
- [ ] 7.1 对政策正文 `content_html` 增加白名单净化渲染（防 XSS）
- [ ] 7.2 增加前端单元测试，覆盖恶意 HTML 清洗场景

## 8. 验证与回归
- [ ] 8.1 后端单元测试：字段映射、限频重试、缓存命中、降级返回
- [ ] 8.2 前端测试：Tab 切换、来源筛选、空态、部分失败提示
- [ ] 8.3 联调验证：6 个 API 真实调用与字段落地
- [ ] 8.4 回归验证：原有 `/api/news/list`、`/api/news/search` 行为保持兼容
- [ ] 8.5 执行 `openspec validate update-news-datasources --strict`
