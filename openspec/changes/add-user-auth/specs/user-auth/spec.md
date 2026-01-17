# User Authentication Specification

## ADDED Requirements

### Requirement: User Registration with Email Whitelist
用户必须使用在白名单中的邮箱进行注册。系统应验证邮箱是否在白名单中，只有白名单内的邮箱才能成功注册。

#### Scenario: Registration with whitelisted email
- **GIVEN** 邮箱 `user@allowed.com` 在白名单中
- **WHEN** 用户使用该邮箱和有效密码提交注册请求
- **THEN** 系统创建新用户账户
- **AND** 返回注册成功响应

#### Scenario: Registration with non-whitelisted email
- **GIVEN** 邮箱 `user@notallowed.com` 不在白名单中
- **WHEN** 用户使用该邮箱提交注册请求
- **THEN** 系统拒绝注册
- **AND** 返回错误信息 "该邮箱不在允许注册的范围内"

#### Scenario: Registration with duplicate email
- **GIVEN** 邮箱 `existing@allowed.com` 已被注册
- **WHEN** 用户使用该邮箱提交注册请求
- **THEN** 系统拒绝注册
- **AND** 返回错误信息 "该邮箱已被注册"

### Requirement: User Login with JWT
用户必须使用邮箱和密码登录，系统验证成功后返回 JWT Token。

#### Scenario: Login with valid credentials
- **GIVEN** 用户 `user@allowed.com` 已注册且密码为 `password123`
- **WHEN** 用户使用正确的邮箱和密码登录
- **THEN** 系统返回有效的 JWT Token
- **AND** Token 包含用户 ID 和过期时间

#### Scenario: Login with invalid password
- **GIVEN** 用户 `user@allowed.com` 已注册
- **WHEN** 用户使用错误的密码登录
- **THEN** 系统拒绝登录
- **AND** 返回错误信息 "邮箱或密码错误"

#### Scenario: Login with non-existent email
- **WHEN** 用户使用未注册的邮箱登录
- **THEN** 系统拒绝登录
- **AND** 返回错误信息 "邮箱或密码错误"

### Requirement: Get Current User
已登录用户可以获取自己的用户信息。

#### Scenario: Get user info with valid token
- **GIVEN** 用户已登录并持有有效 Token
- **WHEN** 用户请求 `/api/auth/me`
- **THEN** 系统返回用户信息（ID、邮箱、用户名、创建时间）

#### Scenario: Get user info with expired token
- **GIVEN** 用户的 Token 已过期
- **WHEN** 用户请求 `/api/auth/me`
- **THEN** 系统返回 401 Unauthorized
- **AND** 返回错误信息 "Token 已过期"

#### Scenario: Get user info without token
- **WHEN** 用户未携带 Token 请求 `/api/auth/me`
- **THEN** 系统返回 401 Unauthorized

### Requirement: User Logout
用户可以退出登录，前端清除本地存储的 Token。

#### Scenario: Logout successfully
- **GIVEN** 用户已登录
- **WHEN** 用户请求退出登录
- **THEN** 前端清除存储的 Token
- **AND** 用户被重定向到登录页面

### Requirement: Portfolio Data User Isolation
用户只能访问自己的持仓数据，持仓表通过 user_id 与用户关联。

#### Scenario: View own portfolio
- **GIVEN** 用户 A 已登录且有持仓数据
- **WHEN** 用户 A 请求持仓列表
- **THEN** 系统只返回用户 A 的持仓数据

#### Scenario: Cannot view other user's portfolio
- **GIVEN** 用户 A 和用户 B 都有持仓数据
- **WHEN** 用户 A 请求持仓列表
- **THEN** 系统不返回用户 B 的持仓数据

### Requirement: Email Whitelist Management
管理员可以管理邮箱白名单，添加或移除允许注册的邮箱。

#### Scenario: Add email to whitelist
- **GIVEN** 管理员已登录
- **WHEN** 管理员添加邮箱 `new@company.com` 到白名单
- **THEN** 该邮箱可以用于注册

#### Scenario: Import whitelist from file
- **GIVEN** 存在包含邮箱列表的文件
- **WHEN** 系统导入该文件
- **THEN** 文件中的所有邮箱被添加到白名单

### Requirement: Frontend Login Page
前端必须提供登录和注册页面，未登录用户访问受保护页面时重定向到登录页。

#### Scenario: Access public pages without login
- **GIVEN** 用户未登录
- **WHEN** 用户访问 `/market` 或 `/toplist` 页面
- **THEN** 页面正常显示，无需登录

#### Scenario: Access protected page without login
- **GIVEN** 用户未登录
- **WHEN** 用户访问受保护页面（/report, /chat, /screener, /portfolio, /etf, /strategy, /backtest, /memory, /datamanage）
- **THEN** 用户被重定向到 `/login` 页面

#### Scenario: Login page UI
- **WHEN** 用户访问登录页面
- **THEN** 页面显示邮箱输入框、密码输入框、登录按钮
- **AND** 页面提供切换到注册表单的选项

#### Scenario: Successful login redirect
- **GIVEN** 用户在登录页面
- **WHEN** 用户成功登录
- **THEN** 用户被重定向到首页 `/market`

### Requirement: Route Protection Configuration
系统必须区分公开页面和受保护页面，只有受保护页面需要登录认证。

#### Scenario: Public routes definition
- **GIVEN** 系统路由配置
- **THEN** 以下路由为公开路由，无需登录：`/login`, `/market`, `/toplist`

#### Scenario: Protected routes definition
- **GIVEN** 系统路由配置
- **THEN** 以下路由为受保护路由，需要登录：`/report`, `/chat`, `/screener`, `/portfolio`, `/etf`, `/strategy`, `/backtest`, `/memory`, `/datamanage`

#### Scenario: Navigation shows login status
- **GIVEN** 用户未登录
- **WHEN** 用户在公开页面查看导航栏
- **THEN** 受保护页面的菜单项显示锁定图标或提示需要登录
