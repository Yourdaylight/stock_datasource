# Change: Optimize startup worker supervision

## Why
本地启动时后台 worker 只启动一次，异常退出后不会自动恢复，影响数据同步稳定性。

## What Changes
- 本地启动增加 worker 监控与重启机制（带退避与最大重启次数限制）
- 退出时停止监控并阻止重启，确保干净关停
- 引入可配置的环境变量（如重启开关、重启间隔、最大重启次数）

## Impact
- Affected specs: data-management
- Affected code: src/stock_datasource/services/http_server.py
