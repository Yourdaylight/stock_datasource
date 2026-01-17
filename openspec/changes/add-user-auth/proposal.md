# Change: 添加用户邮箱注册与认证系统

## Why
当前系统使用硬编码的 `default_user` 作为用户标识，无法支持多用户场景。需要实现用户注册登录功能，支持邮箱白名单验证，并与现有持仓管理系统联动。

## What Changes
- **ADDED**: 用户认证模块 (`modules/auth/`)
  - 用户注册（邮箱白名单验证）
  - 用户登录（JWT Token）
  - 用户信息获取
  - 退出登录
- **ADDED**: 用户表 (`users`) 存储用户信息
- **ADDED**: 邮箱白名单表 (`email_whitelist`) 存储允许注册的邮箱
- **MODIFIED**: 持仓表 (`user_positions`) 与用户表建立关联
- **ADDED**: 前端登录页面和认证状态管理
- **ADDED**: API 认证中间件

## Impact
- Affected specs: `user-auth` (新增)
- Affected code:
  - `src/stock_datasource/modules/auth/` (新增)
  - `src/stock_datasource/modules/portfolio/` (修改 user_id 关联)
  - `src/stock_datasource/services/http_server.py` (添加认证中间件)
  - `frontend/src/views/login/` (新增)
  - `frontend/src/stores/auth.ts` (新增)
  - `frontend/src/router/index.ts` (添加路由守卫)

## Technical Decisions
- **认证方式**: JWT (无状态、易扩展)
- **密码加密**: bcrypt (passlib)
- **用户存储**: ClickHouse (与现有架构一致)
- **Token 有效期**: 7 天
