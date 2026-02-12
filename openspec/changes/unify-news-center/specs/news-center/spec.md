# Spec: news-center

## Overview

将新闻资讯页面升级为统一的资讯中心，并将机构调研、研报数据整合为 Tab 内容，同时将 `/research` 页面精简为财报分析入口。

## MODIFIED Requirements

### Requirement: 资讯中心页面布局

前端 SHALL 将新闻资讯页面 (`/news`) 重设计为 Tab 布局的统一资讯中心，MUST 包含新闻快讯、机构调研、研报数据三个 Tab。

#### Scenario: 默认展示新闻快讯 Tab
- **Given** 用户访问 `/news` 路由
- **When** 页面加载完成
- **Then** 默认激活"新闻快讯"Tab
- **And** 显示两栏布局：左侧新闻列表（含内联筛选工具栏），右侧热点话题和情绪分析

#### Scenario: 切换到机构调研 Tab
- **Given** 用户在资讯中心页面
- **When** 点击"机构调研"Tab
- **Then** 异步加载并显示 InstitutionalSurveyPanel 组件
- **And** 组件功能与原 `/research` 页面中完全一致

#### Scenario: 切换到研报数据 Tab
- **Given** 用户在资讯中心页面
- **When** 点击"研报数据"Tab
- **Then** 异步加载并显示 ResearchReportPanel 组件
- **And** 组件功能与原 `/research` 页面中完全一致

### Requirement: 新闻筛选内联化

前端 MUST 将新闻筛选条件从独立侧栏改为列表上方的内联工具栏，减少页面固定占位。

#### Scenario: 内联筛选工具栏
- **Given** 用户在新闻快讯 Tab
- **When** 查看新闻列表
- **Then** 列表上方显示内联筛选工具栏（来源、时间、分类下拉选择器）
- **And** 不再有独立的左侧筛选面板

#### Scenario: 筛选条件变更
- **Given** 内联筛选工具栏可见
- **When** 用户修改任意筛选条件
- **Then** 新闻列表立即按新条件过滤刷新

### Requirement: 研究数据页面精简

前端 SHALL 将 `/research` 页面精简为仅包含财报分析内容，MUST 移除机构调研和研报数据 Tab。

#### Scenario: 财报分析页面
- **Given** 用户访问 `/research` 路由
- **When** 页面加载完成
- **Then** 仅显示 A 股财报和港股财报两个 Tab
- **And** 侧边栏菜单名称显示为"财报分析"
