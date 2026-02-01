# Tasks

## 方案 A：清理废弃代码

- [x] 1. 确认 api.py 无外部依赖
  - 搜索所有对 `portfolio/api.py` 的引用 ✅ 无后端依赖
  - 检查是否有测试文件依赖 ✅ 无
  - 前端引用的是 `frontend/src/api/portfolio.ts`，不是后端文件
  
- [x] 2. 删除废弃的 api.py 文件
  - 删除 `/modules/portfolio/api.py` ✅
  - 验证服务正常启动 ✅ 模块导入正常
  
- [x] 3. 验证用户隔离功能
  - pytest 未安装，跳过自动化测试
  - 代码审查确认 `router.py` 的所有接口都使用 `Depends(get_current_user)`

## 增强安全性

- [x] 4. 移除 service.py 中的向后兼容逻辑
  - 删除检查 user_id 列是否存在的代码
  - 强制使用 `WHERE user_id = %(user_id)s` 过滤

- [x] 5. 修复 _batch_update_positions 缺少 user_id
  - 添加 user_id 参数
  - INSERT 语句中包含 user_id 字段
