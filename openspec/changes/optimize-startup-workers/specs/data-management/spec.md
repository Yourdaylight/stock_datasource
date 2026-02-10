## ADDED Requirements

### Requirement: 本地启动 worker 监控与重启
系统 SHALL 在本地开发启动时监控后台 worker 进程，并在异常退出时自动重启，避免同步能力中断。

- 系统 SHALL 在本地模式启动 worker 监控器
- 系统 SHALL 在 worker 异常退出时按退避策略重启
- 系统 SHALL 支持配置最大重启次数，超过后停止重启
- 系统 SHALL 在服务关闭时停止监控并不再重启

#### Scenario: worker 异常退出后自动重启
- **GIVEN** 系统处于本地开发模式并已启动 worker
- **WHEN** 任意 worker 异常退出
- **THEN** 系统在退避等待后自动重启该 worker

#### Scenario: 超过最大重启次数后停止重启
- **GIVEN** 该 worker 已连续异常退出且达到最大重启次数
- **WHEN** 再次异常退出
- **THEN** 系统不再重启该 worker并记录告警

#### Scenario: 服务关闭时停止重启
- **GIVEN** 系统正在关闭
- **WHEN** worker 退出
- **THEN** 系统不再重启 worker
