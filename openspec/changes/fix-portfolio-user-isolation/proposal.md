# fix-portfolio-user-isolation

## Type
Code cleanup / Security hardening（无需 spec delta）

## Summary
修复持仓管理模块中存在的用户隔离安全问题。当前 `api.py` 中的接口允许通过 URL 参数传递 `user_id`，存在越权访问风险。

## Problem Statement

### 当前状态分析

经过代码审查，持仓管理模块的用户隔离状态如下：

| 组件 | 文件 | 用户隔离状态 | 说明 |
|------|------|-------------|------|
| router.py | `/modules/portfolio/router.py` | ✅ 安全 | 使用 `Depends(get_current_user)` 从 JWT 获取用户 |
| service.py | `/modules/portfolio/service.py` | ✅ 安全 | 所有方法接受 `user_id` 参数，使用参数化查询 |
| enhanced_service.py | `/modules/portfolio/enhanced_service.py` | ✅ 安全 | 所有方法接受 `user_id` 参数 |
| api.py | `/modules/portfolio/api.py` | ⚠️ **存在风险** | `user_id` 从查询参数获取，可被篡改 |
| 数据库表 | `user_positions` | ✅ 安全 | 包含 `user_id` 字段，按 `user_id` 排序 |

### 核心问题

`api.py` 中的接口直接从查询参数接收 `user_id`：

```python
# api.py 中的问题代码
@router.get("/positions")
async def get_positions(
    user_id: str = Query("default_user", description="用户ID"),  # ⚠️ 安全风险
):
    positions = await service.get_positions(user_id, ...)
```

**风险**：攻击者可以通过修改 URL 参数访问其他用户的数据：
- `GET /api/portfolio/positions?user_id=victim_user_id`

### 好消息

经确认，当前系统只注册了 `router.py`（通过 `modules/__init__.py`），`api.py` **未被注册**，因此目前不存在实际的安全漏洞。

## Proposed Solution

### 方案 A（推荐）: 清理废弃代码

删除未使用的 `api.py` 文件，避免未来被误用：

**优点**：
- 简洁，消除潜在风险源
- 减少代码维护负担

**缺点**：
- 可能有内部工具依赖此文件（需确认）

### 方案 B: 改造 api.py 使用认证

将 `api.py` 中的接口改为使用 `Depends(get_current_user)`：

**优点**：
- 保留兼容性
- 如需暴露 API 可直接使用

**缺点**：
- 与 `router.py` 功能重复

## Impact Analysis

- **安全性**: 当前无实际漏洞（api.py 未注册）
- **代码质量**: 存在废弃代码，应清理
- **向后兼容**: 清理 api.py 不影响现有功能

## Recommendation

建议采用 **方案 A**，删除废弃的 `api.py` 文件。原因：
1. `router.py` 已提供完整的安全实现
2. `api.py` 与 `router.py` 功能高度重复
3. 保留不安全代码存在被误用风险

## Status
- [x] 确认无内部工具依赖 api.py（前端引用的是 `frontend/src/api/portfolio.ts`）
- [x] 已删除 `api.py`
- [x] 验证模块导入正常
- [x] 已完成
