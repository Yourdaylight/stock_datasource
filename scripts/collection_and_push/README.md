# CSV 实时数据流水线 — 启动命令手册

> 适用于 **2C4G** 及以上服务器，纯 Python 脚本，不依赖 Redis / ClickHouse。

---

## 架构总览

```
csv_pipeline.py（控制进程）
  ├── collect  子进程 ×1  — 采集 TuShare 实时行情 → CSV
  ├── push     子进程 ×1  — 增量读取 CSV → 推送云端
  └── cleanup  子进程 ×1  — 定期清理过期 CSV 文件
```

---

## 环境变量（可选）

可以通过环境变量或 `.env` 文件配置，免去命令行传参：

```bash
# .env 文件示例
TUSHARE_TOKEN=your_tushare_token
TUSHARE_API_URL=https://api.tushare.pro        # 可选，覆盖默认 API 地址
HTTP_PROXY=http://127.0.0.1:7890               # 可选，代理
RT_KLINE_CLOUD_PUSH_URL=https://your-cloud/api/v1/rt-kline/push
RT_KLINE_CLOUD_PUSH_TOKEN=your_push_token
CSV_DIR=data/tushare_csv                        # 可选，默认 data/tushare_csv
```

---

## 一、一键启动（推荐）

### 完整流水线：采集 + 推送 + 清理

```bash
python scripts/collection_and_push/csv_pipeline.py \
  --token $TUSHARE_TOKEN \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN
```

### 使用 .env 文件（更简洁）

```bash
python scripts/collection_and_push/csv_pipeline.py --env-file .env
```

### 2C4G 推荐参数

```bash
python scripts/collection_and_push/csv_pipeline.py \
  --env-file .env \
  --collect-interval 2.0 \
  --push-interval 5.0 \
  --cleanup-interval 7200 \
  --max-age-days 2
```

---

## 二、按需组合

### 只采集 + 清理（不推送到云端）

```bash
python scripts/collection_and_push/csv_pipeline.py \
  --token $TUSHARE_TOKEN \
  --disable-push
```

### 只推送（CSV 由其他方式生成）

```bash
python scripts/collection_and_push/csv_pipeline.py \
  --disable-collect --disable-cleanup \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN
```

### 只采集（不推送不清理）

```bash
python scripts/collection_and_push/csv_pipeline.py \
  --token $TUSHARE_TOKEN \
  --disable-push --disable-cleanup
```

---

## 三、单独运行各脚本

如果不想用控制脚本，也可以分别单独启动。

### 3.1 采集脚本 `collect_tushare_to_csv.py`

```bash
# 单次采集（不循环）
python scripts/collection_and_push/collect_tushare_to_csv.py --token $TUSHARE_TOKEN

# 持续循环采集（追加模式，每 2 秒一轮）
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN \
  --loop --interval 2.0 --append

# 指定市场
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN \
  --loop --append \
  --markets a_stock,etf

# 忽略交易时段限制（调试用）
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN \
  --loop --append \
  --ignore-trading-window

# 指定 API 地址和代理
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN \
  --api-url https://api.tushare.pro \
  --proxy-url http://127.0.0.1:7890 \
  --loop --append
```

**常用参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--token` | `$TUSHARE_TOKEN` | TuShare API Token（**必填**） |
| `--markets` | `a_stock,etf,index,hk` | 采集市场（逗号分隔） |
| `--output-dir` | `data/tushare_csv` | CSV 输出目录 |
| `--append` | 关闭 | 追加模式，写入 `{market}.csv` |
| `--loop` | 关闭 | 持续循环采集 |
| `--interval` | `1.5` | 循环间隔（秒） |
| `--rounds` | `0` | 最大轮次，0=无限 |
| `--trading-only` | 开启 | 仅交易时段采集 |
| `--ignore-trading-window` | 关闭 | 忽略交易时段限制 |
| `--idle-sleep` | `30` | 非交易时段休眠秒数 |
| `--api-url` | `$TUSHARE_API_URL` | TuShare API 地址 |
| `--proxy-url` | `$HTTP_PROXY` | HTTP 代理 |
| `--rate-limit` | `50` | 每分钟 API 调用上限 |
| `--market-inner-concurrency` | `3` | 单市场内并发线程数 |

### 3.2 推送脚本 `push_csv_to_cloud.py`

```bash
# 单次推送
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN

# 持续循环推送（每 5 秒检查一次增量）
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN \
  --loop --interval 5.0

# 指定市场和批量大小
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --markets a_stock,etf \
  --batch-size 500 \
  --loop
```

**常用参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--push-url` | `$RT_KLINE_CLOUD_PUSH_URL` | 云端推送 URL（**必填**） |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | 鉴权 Token |
| `--csv-dir` | `data/tushare_csv` | CSV 文件目录 |
| `--markets` | `a_stock,etf,index,hk` | 要推送的市场 |
| `--batch-size` | `1000` | 每批推送条数 |
| `--loop` | 关闭 | 持续循环推送 |
| `--interval` | `3.0` | 循环间隔（秒） |
| `--checkpoint-file` | `data/push_checkpoint.json` | 断点记录文件 |
| `--max-retry` | `3` | 单批最大重试次数 |
| `--timeout` | `15` | HTTP 超时（秒） |

### 3.3 清理脚本 `cleanup_csv.py`

```bash
# 预览将要删除的文件（不实际删除）
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --dry-run

# 清理 2 天以外的 CSV（一次性）
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv

# 清理 1 天以外的 CSV
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --max-age-days 1

# 循环模式（每 2 小时清理一次）
python scripts/collection_and_push/cleanup_csv.py \
  --csv-dir data/tushare_csv \
  --loop --interval 7200

# 清理 12 小时以外的（支持小数）
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --max-age-days 0.5
```

**常用参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--csv-dir` | `data/tushare_csv` | CSV 文件目录 |
| `--max-age-days` | `2` | 保留天数，超过则清理（支持小数） |
| `--dry-run` | 关闭 | 预览模式，只打印不删除 |
| `--loop` | 关闭 | 循环模式 |
| `--interval` | `3600` | 循环间隔（秒） |
| `--no-clean-checkpoint` | 关闭 | 不清理 checkpoint 中的过期记录 |

---

## 四、Pipeline 控制参数总览

`csv_pipeline.py` 把所有子脚本的参数统一到一个命令行：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| **全局** | | |
| `--env-file` | 无 | 加载 .env 文件 |
| `--csv-dir` | `data/tushare_csv` | 三个子流程共享的 CSV 目录 |
| `--markets` | `a_stock,etf,index,hk` | 市场列表 |
| `--log-level` | `INFO` | 日志级别 |
| `--max-restarts` | `10` | 子进程最大重启次数（5 分钟窗口） |
| `--restart-delay` | `3.0` | 重启延迟（秒） |
| **开关** | | |
| `--disable-collect` | 关闭 | 禁用采集 |
| `--disable-push` | 关闭 | 禁用推送 |
| `--disable-cleanup` | 关闭 | 禁用清理 |
| **采集** | | |
| `--token` | `$TUSHARE_TOKEN` | TuShare Token |
| `--api-url` | `$TUSHARE_API_URL` | TuShare API 地址 |
| `--proxy-url` | `$HTTP_PROXY` | HTTP 代理 |
| `--collect-interval` | `1.5` | 采集间隔（秒） |
| `--collect-append` | 开启 | 追加模式 |
| `--no-collect-append` | 关闭 | 关闭追加模式 |
| `--trading-only` | 开启 | 仅交易时段 |
| `--ignore-trading-window` | 关闭 | 忽略交易时段 |
| **推送** | | |
| `--push-url` | `$RT_KLINE_CLOUD_PUSH_URL` | 推送 URL |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | 推送 Token |
| `--push-interval` | `3.0` | 推送间隔（秒） |
| `--batch-size` | `1000` | 每批条数 |
| **清理** | | |
| `--max-age-days` | `2.0` | 保留天数 |
| `--cleanup-interval` | `3600` | 清理间隔（秒） |

---

## 五、后台运行

### 使用 nohup

```bash
nohup python scripts/collection_and_push/csv_pipeline.py --env-file .env \
  --collect-interval 2.0 --push-interval 5.0 \
  > logs/csv_pipeline.log 2>&1 &
```

### 使用 systemd（推荐生产环境）

创建 `/etc/systemd/system/csv-pipeline.service`：

```ini
[Unit]
Description=CSV Realtime Pipeline
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/path/to/stock_datasource
EnvironmentFile=/path/to/stock_datasource/.env
ExecStart=/usr/bin/python3 scripts/collection_and_push/csv_pipeline.py \
  --env-file .env \
  --collect-interval 2.0 \
  --push-interval 5.0 \
  --cleanup-interval 7200
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable csv-pipeline
sudo systemctl start csv-pipeline
sudo systemctl status csv-pipeline

# 查看日志
journalctl -u csv-pipeline -f
```

---

## 六、常见场景速查

| 场景 | 命令 |
|------|------|
| 开发调试（忽略交易时段） | `python scripts/collection_and_push/csv_pipeline.py --env-file .env --ignore-trading-window --disable-push` |
| 生产环境一键启动 | `python scripts/collection_and_push/csv_pipeline.py --env-file .env --collect-interval 2.0 --push-interval 5.0` |
| 只跑采集看数据 | `python scripts/collection_and_push/collect_tushare_to_csv.py --token $TUSHARE_TOKEN --append --ignore-trading-window` |
| 检查哪些 CSV 会被清理 | `python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --dry-run` |
| 手动推送一次 | `python scripts/collection_and_push/push_csv_to_cloud.py --push-url $RT_KLINE_CLOUD_PUSH_URL` |
| 后台常驻（nohup） | `nohup python scripts/collection_and_push/csv_pipeline.py --env-file .env > logs/pipeline.log 2>&1 &` |

---

## 七、注意事项

1. **2C4G 服务器建议**：`--collect-interval 2.0`、`--push-interval 5.0`，降低 CPU/内存压力
2. **API 限频**：TuShare 默认 50 次/分钟，脚本内置限频器，无需额外配置
3. **数据安全**：清理前先用 `--dry-run` 预览，确认无误再执行
4. **磁盘空间**：追加模式下 CSV 文件会持续增长，建议 `--max-age-days 2` 定期清理
5. **断点续传**：推送脚本使用 `push_checkpoint.json` 记录进度，重启后自动续传
6. **崩溃恢复**：Pipeline 控制脚本自动重启崩溃的子进程（5 分钟内最多 10 次）
