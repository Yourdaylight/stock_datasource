# Tasks: 用户邮箱注册与认证系统

## 1. 数据库层
- [x] 1.1 创建 `users` 表 schema 定义
- [x] 1.2 创建 `email_whitelist` 表 schema 定义
- [x] 1.3 创建数据库迁移脚本 (`schema.sql`)

## 2. 后端认证模块
- [x] 2.1 创建 `modules/auth/` 目录结构
- [x] 2.2 实现 `schemas.py` (Pydantic 模型)
- [x] 2.3 实现 `service.py` (业务逻辑: 注册、登录、验证)
- [x] 2.4 实现 `router.py` (API 路由)
- [x] 2.5 实现 `dependencies.py` (认证依赖: get_current_user)
- [x] 2.6 实现 JWT Token 生成和验证
- [x] 2.7 实现密码哈希 (bcrypt)

## 3. 后端集成
- [x] 3.1 在 `http_server.py` 注册 auth 路由
- [x] 3.2 添加认证中间件（可选路由保护）
- [x] 3.3 修改 portfolio 模块使用当前用户 ID

## 4. 前端认证
- [x] 4.1 创建 `api/auth.ts` (API 封装)
- [x] 4.2 创建 `stores/auth.ts` (Pinia 状态管理)
- [x] 4.3 创建 `views/login/LoginView.vue` (登录/注册页面)
- [x] 4.4 添加路由守卫 (未登录跳转登录页)
- [x] 4.5 修改 `App.vue` 显示当前用户信息

## 5. 白名单管理
- [x] 5.1 实现白名单导入功能
- [x] 5.2 实现白名单管理 API

## 6. 测试与验证
- [x] 6.1 测试注册流程（白名单内/外）
- [x] 6.2 测试登录流程
- [x] 6.3 测试持仓数据用户隔离
- [x] 6.4 测试 Token 过期处理
