## ADDED Requirements
### Requirement: Unified Backtest Entry
系统 SHALL 在策略工具台提供回测入口与回测历史记录展示，作为主要使用路径。

#### Scenario: View recent backtest history
- **WHEN** 用户进入策略工具台的回测结果区域
- **THEN** 系统展示最近回测记录列表

### Requirement: Hide duplicate backtest entry
系统 SHALL 隐藏“策略回测”导航入口，但保留原有路由以兼容旧链接。

#### Scenario: Legacy access still works
- **WHEN** 用户通过旧链接访问策略回测页面
- **THEN** 页面仍可正常访问
