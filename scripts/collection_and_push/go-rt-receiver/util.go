package main

import (
	"flag"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// ReceiverConfig mirrors the Python ReceiverConfig dataclass.
type ReceiverConfig struct {
	Host                    string
	Port                    int
	Token                   string
	PushToken               string
	PolicyToken             string
	JWTPublicKeyPath        string
	DataDir                 string
	SpoolDir                string
	SnapshotDir             string
	SQLitePath              string
	SaveCSV                 bool
	FlushIntervalSeconds    int
	FlushMaxItems           int
	SubscriptionStepSeconds int
	Timezone                string
	LogLevel                string
	Debug                   bool
}

func envOrDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func envIntOrDefault(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func ParseConfig() ReceiverConfig {
	host := flag.String("host", "0.0.0.0", "监听地址")
	port := flag.Int("port", envIntOrDefault("RT_RECEIVER_PORT", 9100), "监听端口")
	token := flag.String("token", envOrDefault("RT_KLINE_CLOUD_PUSH_TOKEN", ""), "兼容旧参数，等同 --push-token")
	pushToken := flag.String("push-token", envOrDefault("RT_KLINE_CLOUD_PUSH_TOKEN", ""), "Push 写入 Bearer Token")
	policyToken := flag.String("policy-token", envOrDefault("RT_STOCK_POLICY_TOKEN", ""), "Policy 快照 Bearer Token")
	jwtPubKey := flag.String("jwt-public-key-path", envOrDefault("RT_STOCK_JWT_PUBLIC_KEY_PATH", ""), "JWT 公钥路径")
	dataDir := flag.String("data-dir", "data/received_push", "数据根目录")
	spoolDir := flag.String("spool-dir", envOrDefault("RT_KLINE_SPOOL_DIR", ""), "spool 追加写目录")
	snapshotDir := flag.String("snapshot-dir", envOrDefault("RT_KLINE_SNAPSHOT_DIR", ""), "SQLite/CSV 快照目录")
	sqlitePath := flag.String("sqlite-path", envOrDefault("RT_KLINE_SQLITE_PATH", ""), "SQLite 快照文件路径")
	saveCSV := flag.Bool("save-csv", false, "每次刷盘后导出市场级最新 CSV")
	flushInterval := flag.Int("flush-interval-seconds", 3, "builder 批量刷 SQLite 间隔")
	flushMax := flag.Int("flush-max-items", 10000, "单次 builder 最多处理的 spool 记录数")
	subStep := flag.Int("subscription-step-seconds", 3, "订阅查询时间步长")
	tz := flag.String("timezone", envOrDefault("RT_RECEIVER_TIMEZONE", "Asia/Shanghai"), "清理使用的时区")
	logLevel := flag.String("log-level", "INFO", "日志级别")
	debug := flag.Bool("debug", false, "开发调试模式")

	flag.Parse()

	pt := strings.TrimSpace(*pushToken)
	if pt == "" {
		pt = strings.TrimSpace(*token)
	}

	return ReceiverConfig{
		Host:                    *host,
		Port:                    *port,
		Token:                   strings.TrimSpace(*token),
		PushToken:               pt,
		PolicyToken:             strings.TrimSpace(*policyToken),
		JWTPublicKeyPath:        strings.TrimSpace(*jwtPubKey),
		DataDir:                 *dataDir,
		SpoolDir:                *spoolDir,
		SnapshotDir:             *snapshotDir,
		SQLitePath:              *sqlitePath,
		SaveCSV:                 *saveCSV,
		FlushIntervalSeconds:    maxInt(1, *flushInterval),
		FlushMaxItems:           maxInt(100, *flushMax),
		SubscriptionStepSeconds: maxInt(1, *subStep),
		Timezone:                *tz,
		LogLevel:                strings.ToUpper(*logLevel),
		Debug:                   *debug,
	}
}

func (c ReceiverConfig) ListenAddr() string {
	return fmt.Sprintf("%s:%d", c.Host, c.Port)
}

// ── Time helpers ────────────────────────────────────────────────

func utcNowISO() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

func utcNowISOAt(t time.Time) string {
	return t.UTC().Format(time.RFC3339Nano)
}
