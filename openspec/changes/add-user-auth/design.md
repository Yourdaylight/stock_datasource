# Design: 用户邮箱注册与认证系统

## Context
当前系统是单用户模式，所有持仓数据使用 `default_user` 标识。需要支持多用户场景，每个用户管理自己的持仓数据。

### 约束
- 只有在邮箱白名单中的用户才能注册
- 需要与现有 ClickHouse 数据库架构兼容
- 前端使用 Vue 3 + TDesign

## Goals / Non-Goals

### Goals
- 实现邮箱白名单注册
- 实现 JWT 登录认证
- 用户与持仓数据关联
- 前端登录页面和路由守卫

### Non-Goals
- 邮箱验证码（暂不实现）
- 密码找回功能（暂不实现）
- OAuth 第三方登录（暂不实现）
- 用户权限角色管理（暂不实现）

## Decisions

### 1. 数据库设计

#### users 表
```sql
CREATE TABLE IF NOT EXISTS users (
    id String,
    email String,
    username String,
    password_hash String,
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (email, id)
SETTINGS index_granularity = 8192;
```

#### email_whitelist 表
```sql
CREATE TABLE IF NOT EXISTS email_whitelist (
    id String,
    email String,
    added_by String DEFAULT 'system',
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (email, id)
SETTINGS index_granularity = 8192;
```

### 2. API 设计

| 接口 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/auth/register` | POST | 用户注册 | 否 |
| `/api/auth/login` | POST | 用户登录 | 否 |
| `/api/auth/me` | GET | 获取当前用户 | 是 |
| `/api/auth/logout` | POST | 退出登录 | 是 |
| `/api/auth/whitelist` | GET | 获取白名单（管理） | 是 |
| `/api/auth/whitelist` | POST | 添加白名单（管理） | 是 |

### 3. 认证流程

```
1. 注册流程:
   用户提交邮箱+密码 → 验证邮箱在白名单 → 创建用户 → 返回成功

2. 登录流程:
   用户提交邮箱+密码 → 验证密码 → 生成 JWT Token → 返回 Token

3. 请求认证:
   请求携带 Authorization: Bearer <token> → 中间件验证 → 注入用户信息
```

### 4. 前端架构

```
frontend/src/
├── api/
│   └── auth.ts              # 认证 API 封装
├── stores/
│   └── auth.ts              # Pinia 认证状态
├── views/
│   └── login/
│       └── index.vue        # 登录/注册页面
└── router/
    └── index.ts             # 添加路由守卫
```

### 5. 路由权限配置

| 页面 | 路径 | 需要登录 |
|------|------|:--------:|
| 登录页 | /login | ❌ |
| 行情分析 | /market | ❌ |
| 龙虎榜分析 | /toplist | ❌ |
| 财报研读 | /report | ✅ |
| 智能对话 | /chat | ✅ |
| 智能选股 | /screener | ✅ |
| 持仓管理 | /portfolio | ✅ |
| 智能选ETF | /etf | ✅ |
| 策略工具台 | /strategy | ✅ |
| 策略回测 | /backtest | ✅ |
| 用户记忆 | /memory | ✅ |
| 数据管理 | /datamanage | ✅ |

**公开路由**: `/login`, `/market`, `/toplist`
**受保护路由**: 其他所有页面

### 6. 持仓表联动

现有 `user_positions` 表已有 `user_id` 字段，只需：
- 新用户注册后，使用其 `id` 作为 `user_id`
- 查询持仓时，根据当前登录用户的 `id` 过滤

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| ClickHouse 不适合频繁更新 | 用户表数据量小，影响可控 |
| JWT Token 泄露 | 设置合理过期时间，前端安全存储 |
| 邮箱白名单管理 | 提供管理接口，支持动态添加 |

## Migration Plan

1. 创建 `users` 和 `email_whitelist` 表
2. 导入初始邮箱白名单
3. 部署后端认证模块
4. 部署前端登录页面
5. 现有 `default_user` 数据可保留，新用户使用新 ID

## Open Questions

- [ ] 是否需要用户名（username）还是只用邮箱？
- [ ] Token 过期时间设置为多久？（建议 7 天）
- [ ] 是否需要"记住我"功能？

## 邮箱白名单

白名单来源：`email.txt`，共 **287 个邮箱**，全部为 `@tencent.com` 域名。

系统启动时自动从 `email.txt` 加载白名单到 `email_whitelist` 表。
