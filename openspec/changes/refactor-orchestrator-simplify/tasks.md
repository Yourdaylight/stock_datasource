## 1. Implementation

- [x] 1.1 Create `refactor/orchestrator-simplify` branch from clean `main`.
- [x] 1.2 Rewrite `orchestrator.py` to use config-driven harness dispatch only.
- [x] 1.3 Remove `HARNESS_MODE_ENABLED` and `AGENT_RUNTIME_ENABLED` code paths.
- [x] 1.4 Delete `agent_runtime.py` and deprecated agent files.
- [x] 1.5 Update imports/routes/tests/docs that referenced removed files.
- [x] 1.6 Mark retained legacy direct-import agents as deprecated.
- [x] 1.7 Run reference search, compile checks, and targeted tests.
