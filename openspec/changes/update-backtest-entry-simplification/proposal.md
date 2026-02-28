# Change: Simplify backtest entry and consolidate history

## Why
策略回测与策略工具台存在重复入口，容易造成用户困惑和结果口径不一致。

## What Changes
- 在策略工具台中增加回测历史记录展示
- 将“策略回测”入口从导航/菜单中隐藏（保留页面以兼容旧链接）

## Impact
- Affected specs: backtest-experience
- Affected code: frontend routing/navigation, StrategyWorkbench backtest views
