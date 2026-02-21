# Spec: news-performance

## Overview

优化新闻资讯模块性能：将情绪分析从主请求路径解耦为后台异步任务，启用前端缓存层，添加骨架屏超时降级与情绪标签降级显示。

## MODIFIED Requirements

### Requirement: 新闻列表接口响应时间优化

系统 SHALL 将情绪分析从新闻列表主请求路径中解耦。`get_market_news()` MUST 直接返回已有数据（含已存储的 sentiment），对缺少 sentiment 的新闻异步触发后台分析。

#### Scenario: 缓存命中时快速返回
- **Given** 文件缓存中已有新闻数据（含历史 sentiment 结果）
- **When** 前端请求 `/api/news/list`
- **Then** 接口在 500ms 内返回新闻列表
- **And** 已分析过的新闻带有 sentiment 字段
- **And** 未分析的新闻 sentiment 为 null

#### Scenario: 缓存未命中时也快速返回
- **Given** 文件缓存中无数据，需从外部 API 获取
- **When** 前端请求 `/api/news/list`
- **Then** 接口在外部 API 响应后立即返回新闻列表（不等待情绪分析）
- **And** sentiment 字段全部为 null
- **And** 后台异步任务开始执行情绪分析

#### Scenario: 后台情绪分析完成后结果持久化
- **Given** 后台异步情绪分析完成
- **When** 下一次请求 `/api/news/list`
- **Then** 返回的新闻数据包含已分析的 sentiment 结果

### Requirement: 情绪分析结果持久化

系统 MUST 将情绪分析结果随新闻数据一同保存到本地文件存储，避免重复 LLM 调用。

#### Scenario: 已分析的新闻不重复分析
- **Given** 某条新闻已有 sentiment 结果（保存在文件中）
- **When** 后台情绪分析任务执行
- **Then** 跳过该新闻，不调用 LLM

### Requirement: 前端缓存层启用

前端 SHALL 将已实现的 `NewsCacheManager` 接入 Pinia Store 层，短时间内重复请求 MUST 直接返回前端缓存。

#### Scenario: 前端缓存命中
- **Given** 5 分钟内已成功获取过新闻数据
- **When** 用户再次进入新闻页面或切换回来
- **Then** 直接使用前端缓存数据渲染，不发起 HTTP 请求

#### Scenario: 前端缓存过期
- **Given** 上次获取新闻超过 5 分钟
- **When** 用户进入新闻页面
- **Then** 发起新的 HTTP 请求获取最新数据

### Requirement: 骨架屏超时降级

前端 MUST 为骨架屏设置最大显示时间，超时后提供用户可操作的降级 UI。

#### Scenario: 加载超时
- **Given** 新闻列表请求已发出
- **When** 超过 10 秒仍未收到响应
- **Then** 骨架屏消失，显示"加载超时"提示和重试按钮

### Requirement: 新闻卡片 sentiment 降级显示

前端 MUST 对 sentiment 为 null 的新闻卡片进行优雅降级显示。

#### Scenario: 无情绪数据的新闻卡片
- **Given** 新闻的 sentiment 字段为 null
- **When** 渲染新闻卡片
- **Then** 不显示情绪标签区域（或显示"分析中"占位符）
- **And** 卡片布局正常，无报错

### Requirement: 初始加载避免重复请求

前端 SHALL 优化新闻页面初始加载逻辑，避免重复触发相同的新闻数据请求。

#### Scenario: 首次加载仅请求一次新闻列表
- **Given** 用户首次进入新闻页面
- **When** 页面初始化并行请求触发
- **Then** 后端只收到一次新闻列表获取请求
