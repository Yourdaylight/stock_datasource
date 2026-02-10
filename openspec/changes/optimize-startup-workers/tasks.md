## 1. Implementation
- [x] Add worker supervisor with restart/backoff in local dev startup
- [x] Add shutdown flag to stop restarts on shutdown
- [x] Add env-configurable parameters for restart behavior
- [x] Update logging to include restart events

## 2. Tests
- [x] Manual run: start server, kill a worker, verify restart
- [x] Manual run: shutdown server, verify no restarts
