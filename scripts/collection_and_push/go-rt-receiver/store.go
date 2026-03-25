package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type tickUpdate struct {
	Market     string
	TSCode     string
	PayloadJSON string
	SourceAPI  string
	BatchSeq   int
	EventTime  string
	ReceivedAt string
	UpdatedAt  string
}

type PushDataStore struct {
	cfg         ReceiverConfig
	baseDir     string
	spoolDir    string
	snapshotDir string
	dbPath      string
	location    *time.Location
	db          *sql.DB
	spoolMu     sync.Mutex
	cleanupMu   sync.Mutex
	stopCh      chan struct{}
	wg          sync.WaitGroup
	wsHub       *WSHub // WebSocket Hub，可选
}

func NewPushDataStore(cfg ReceiverConfig) (*PushDataStore, error) {
	loc, err := time.LoadLocation(cfg.Timezone)
	if err != nil {
		return nil, fmt.Errorf("load timezone %s: %w", cfg.Timezone, err)
	}

	baseDir := cfg.DataDir
	spoolDir := cfg.SpoolDir
	if strings.TrimSpace(spoolDir) == "" {
		spoolDir = filepath.Join(baseDir, "spool")
	}
	snapshotDir := cfg.SnapshotDir
	if strings.TrimSpace(snapshotDir) == "" {
		snapshotDir = filepath.Join(baseDir, "snapshot")
	}
	dbPath := cfg.SQLitePath
	if strings.TrimSpace(dbPath) == "" {
		dbPath = filepath.Join(snapshotDir, "rt_snapshot.db")
	}

	for _, dir := range []string{baseDir, spoolDir, snapshotDir} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, fmt.Errorf("mkdir %s: %w", dir, err)
		}
	}

	dsn := fmt.Sprintf("file:%s?_busy_timeout=30000&_journal_mode=WAL&_synchronous=NORMAL&_temp_store=MEMORY", filepath.ToSlash(dbPath))
	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	db.SetConnMaxLifetime(0)
	db.SetMaxIdleConns(4)
	db.SetMaxOpenConns(4)

	store := &PushDataStore{
		cfg:         cfg,
		baseDir:     baseDir,
		spoolDir:    spoolDir,
		snapshotDir: snapshotDir,
		dbPath:      dbPath,
		location:    loc,
		db:          db,
		stopCh:      make(chan struct{}),
	}
	if err := store.initDB(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return store, nil
}

func (s *PushDataStore) StartBuilder() {
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		s.builderLoop()
	}()
}

func (s *PushDataStore) Stop() {
	close(s.stopCh)
	s.wg.Wait()
	_ = s.db.Close()
}

func (s *PushDataStore) initDB() error {
	schema := `
	CREATE TABLE IF NOT EXISTS latest_ticks (
		market TEXT NOT NULL,
		ts_code TEXT NOT NULL,
		payload_json TEXT NOT NULL,
		source_api TEXT NOT NULL DEFAULT '',
		batch_seq INTEGER NOT NULL DEFAULT 0,
		event_time TEXT NOT NULL DEFAULT '',
		received_at TEXT NOT NULL DEFAULT '',
		updated_at TEXT NOT NULL DEFAULT '',
		PRIMARY KEY (market, ts_code)
	);
	CREATE INDEX IF NOT EXISTS idx_latest_ticks_ts_code ON latest_ticks(ts_code);

	CREATE TABLE IF NOT EXISTS ingest_offsets (
		file_path TEXT PRIMARY KEY,
		offset INTEGER NOT NULL DEFAULT 0,
		updated_at TEXT NOT NULL DEFAULT ''
	);

	CREATE TABLE IF NOT EXISTS user_policies (
		user_id TEXT PRIMARY KEY,
		payload_json TEXT NOT NULL,
		revision INTEGER NOT NULL DEFAULT 0,
		updated_at TEXT NOT NULL DEFAULT ''
	);

	CREATE TABLE IF NOT EXISTS user_subscriptions (
		user_id TEXT NOT NULL,
		ts_code TEXT NOT NULL,
		updated_at TEXT NOT NULL DEFAULT '',
		PRIMARY KEY (user_id, ts_code)
	);
	CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);

	CREATE TABLE IF NOT EXISTS runtime_meta (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL,
		updated_at TEXT NOT NULL DEFAULT ''
	);
	`
	_, err := s.db.Exec(schema)
	if err != nil {
		return fmt.Errorf("init sqlite schema: %w", err)
	}
	return nil
}

func (s *PushDataStore) builderLoop() {
	consecutiveEmpty := 0
	for {
		select {
		case <-s.stopCh:
			return
		default:
		}

		if err := s.maybeRunDailyCleanup(); err != nil {
			log.Printf("[ERROR] daily cleanup failed: %v", err)
		}

		processed, upserts, err := s.processSpoolOnce(s.cfg.FlushMaxItems)
		if err != nil {
			log.Printf("[ERROR] snapshot builder failed: %v", err)
			consecutiveEmpty++
		} else if processed > 0 {
			log.Printf("[INFO] flushed spool to sqlite processed=%d upserts=%d", processed, upserts)
			consecutiveEmpty = 0
			if processed >= s.cfg.FlushMaxItems {
				continue
			}
		} else {
			consecutiveEmpty++
		}

		waitSeconds := s.cfg.FlushIntervalSeconds
		if consecutiveEmpty <= 2 && waitSeconds > 1 {
			waitSeconds = 1
		}

		select {
		case <-s.stopCh:
			return
		case <-time.After(time.Duration(waitSeconds) * time.Second):
		}
	}
}

func (s *PushDataStore) maybeRunDailyCleanup() error {
	now := time.Now().In(s.location)
	if now.Hour() < 9 {
		return nil
	}
	todayKey := now.Format("20060102")
	lastCleanup, err := s.getMeta("last_daily_cleanup_date")
	if err != nil {
		return err
	}
	if lastCleanup == todayKey {
		return nil
	}
	return s.performDailyCleanup(todayKey)
}

func (s *PushDataStore) performDailyCleanup(todayKey string) error {
	s.cleanupMu.Lock()
	defer s.cleanupMu.Unlock()

	lastCleanup, err := s.getMeta("last_daily_cleanup_date")
	if err != nil {
		return err
	}
	if lastCleanup == todayKey {
		return nil
	}

	deletedFiles := 0
	s.spoolMu.Lock()
	files, err := s.iterSpoolFiles()
	if err == nil {
		for _, filePath := range files {
			dateKey := strings.TrimSuffix(filepath.Base(filePath), filepath.Ext(filePath))
			if dateKey == todayKey {
				continue
			}
			if removeErr := os.Remove(filePath); removeErr == nil || errors.Is(removeErr, os.ErrNotExist) {
				deletedFiles++
			} else {
				s.spoolMu.Unlock()
				return fmt.Errorf("delete spool %s: %w", filePath, removeErr)
			}
		}
	}
	s.cleanupEmptySpoolDirs()
	s.spoolMu.Unlock()
	if err != nil {
		return err
	}

	ctx := context.Background()
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	rollback := true
	defer func() {
		if rollback {
			_ = tx.Rollback()
		}
	}()

	for _, stmt := range []string{
		"DELETE FROM latest_ticks",
		"DELETE FROM ingest_offsets",
		"DELETE FROM runtime_meta WHERE key IN ('last_flush_at', 'last_flush_items')",
	} {
		if _, err := tx.ExecContext(ctx, stmt); err != nil {
			return fmt.Errorf("daily cleanup sql %q: %w", stmt, err)
		}
	}

	if err := upsertMetaTx(ctx, tx, "last_daily_cleanup_date", todayKey); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	rollback = false

	if err := s.removeSnapshotCSVs(); err != nil {
		log.Printf("[WARN] remove snapshot csv failed: %v", err)
	}
	if _, err := s.db.Exec("VACUUM"); err != nil {
		log.Printf("[WARN] sqlite VACUUM failed: %v", err)
	}

	log.Printf("[INFO] daily 09:00 cleanup finished, preserved=%s deleted_spool=%d", todayKey, deletedFiles)

	for {
		processed, _, err := s.processSpoolOnce(s.cfg.FlushMaxItems)
		if err != nil {
			return err
		}
		if processed == 0 || processed < s.cfg.FlushMaxItems {
			break
		}
	}
	return nil
}

func (s *PushDataStore) StoreBatch(payload map[string]any) map[string]any {
	market := asString(payload["market"])
	items, _ := payload["items"].([]any)
	batchSeq, _ := intFromAny(payload["batch_seq"])
	eventTime := asString(payload["event_time"])
	sourceAPI := asString(payload["source_api"])
	now := time.Now()
	receivedAt := utcNowISOAt(now)
	spoolPath := s.spoolFilePath(market, now)

	records := make([]map[string]any, 0, len(items))
	for _, rawItem := range items {
		item, ok := rawItem.(map[string]any)
		if !ok {
			continue
		}
		tsCode := strings.ToUpper(strings.TrimSpace(asString(item["ts_code"])))
		tick, ok := item["tick"].(map[string]any)
		if !ok || tsCode == "" {
			continue
		}
		tick["ts_code"] = tsCode
		tick["market"] = market
		records = append(records, map[string]any{
			"received_at": receivedAt,
			"market":      market,
			"batch_seq":   batchSeq,
			"event_time":  eventTime,
			"source_api":  sourceAPI,
			"stream_id":   asString(item["stream_id"]),
			"ts_code":     tsCode,
			"shard_id":    item["shard_id"],
			"tick":        tick,
		})
	}

	if len(records) > 0 {
		if err := os.MkdirAll(filepath.Dir(spoolPath), 0o755); err != nil {
			panic(err)
		}
		s.spoolMu.Lock()
		func() {
			defer s.spoolMu.Unlock()
			file, err := os.OpenFile(spoolPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
			if err != nil {
				panic(err)
			}
			defer file.Close()
			for _, record := range records {
				line, err := json.Marshal(record)
				if err != nil {
					continue
				}
				_, _ = file.Write(append(line, '\n'))
			}
			_ = file.Sync()
		}()

		// ── WebSocket 实时广播 ──────────────────────────
		if s.wsHub != nil && s.wsHub.ClientCount() > 0 {
			ticks := make([]tickBroadcast, 0, len(records))
			for _, record := range records {
				tick, _ := record["tick"].(map[string]any)
				if tick == nil {
					continue
				}
				ticks = append(ticks, tickBroadcast{
					Market:      asString(record["market"]),
					TSCode:      asString(record["ts_code"]),
					PayloadJSON: tick,
					BatchSeq:    mustInt(record["batch_seq"]),
					EventTime:   asString(record["event_time"]),
					SourceAPI:   asString(record["source_api"]),
					ReceivedAt:  asString(record["received_at"]),
				})
			}
			s.wsHub.BroadcastTicks(ticks)
		}
	}

	return map[string]any{
		"status":         "ok",
		"code":           0,
		"ack_seq":        batchSeq,
		"accepted_count": len(records),
		"rejected_count": maxInt(0, len(items)-len(records)),
	}
}

func (s *PushDataStore) spoolFilePath(market string, now time.Time) string {
	dateKey := now.In(s.location).Format("20060102")
	return filepath.Join(s.spoolDir, market, dateKey+".jsonl")
}

func (s *PushDataStore) iterSpoolFiles() ([]string, error) {
	entries, err := os.ReadDir(s.spoolDir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}

	marketDirs := make([]string, 0)
	for _, entry := range entries {
		if entry.IsDir() {
			marketDirs = append(marketDirs, filepath.Join(s.spoolDir, entry.Name()))
		}
	}
	sort.Strings(marketDirs)

	files := make([]string, 0)
	for _, marketDir := range marketDirs {
		matches, err := filepath.Glob(filepath.Join(marketDir, "*.jsonl"))
		if err != nil {
			return nil, err
		}
		sort.Strings(matches)
		files = append(files, matches...)
	}
	return files, nil
}

func (s *PushDataStore) processSpoolOnce(maxItems int) (int, int, error) {
	files, err := s.iterSpoolFiles()
	if err != nil {
		return 0, 0, err
	}

	processed := 0
	updates := map[string]tickUpdate{}
	newOffsets := map[string]int64{}
	touchedMarkets := map[string]struct{}{}

	for _, spoolFile := range files {
		fileKey, err := filepath.Abs(spoolFile)
		if err != nil {
			fileKey = spoolFile
		}

		offset, err := s.readOffset(fileKey)
		if err != nil {
			return 0, 0, err
		}

		file, err := os.Open(spoolFile)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				continue
			}
			return 0, 0, err
		}

		newOffset := offset
		if _, err := file.Seek(offset, io.SeekStart); err != nil {
			_ = file.Close()
			return 0, 0, err
		}

		reader := bufio.NewReader(file)
		stop := false
		for {
			lineStart := newOffset
			line, readErr := reader.ReadBytes('\n')
			if readErr != nil {
				if errors.Is(readErr, io.EOF) {
					break
				}
				_ = file.Close()
				return 0, 0, readErr
			}
			if len(line) == 0 || line[len(line)-1] != '\n' {
				newOffset = lineStart
				break
			}
			newOffset += int64(len(line))

			var record map[string]any
			if err := json.Unmarshal(bytesTrimSpace(line), &record); err != nil {
				continue
			}
			market := strings.TrimSpace(asString(record["market"]))
			tsCode := strings.ToUpper(strings.TrimSpace(asString(record["ts_code"])))
			tick, ok := record["tick"].(map[string]any)
			if !ok || market == "" || tsCode == "" {
				continue
			}
			tick["ts_code"] = tsCode
			tick["market"] = market
			payloadJSON, err := json.Marshal(tick)
			if err != nil {
				continue
			}
			updates[market+"\x00"+tsCode] = tickUpdate{
				Market:      market,
				TSCode:      tsCode,
				PayloadJSON: string(payloadJSON),
				SourceAPI:   asString(record["source_api"]),
				BatchSeq:    mustInt(record["batch_seq"]),
				EventTime:   asString(record["event_time"]),
				ReceivedAt:  asString(record["received_at"]),
				UpdatedAt:   utcNowISO(),
			}
			touchedMarkets[market] = struct{}{}
			processed++
			if maxItems > 0 && processed >= maxItems {
				stop = true
				break
			}
		}
		_ = file.Close()

		if newOffset != offset {
			newOffsets[fileKey] = newOffset
		}
		if stop {
			break
		}
	}

	if len(newOffsets) == 0 && len(updates) == 0 {
		return 0, 0, nil
	}

	ctx := context.Background()
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return 0, 0, err
	}
	rollback := true
	defer func() {
		if rollback {
			_ = tx.Rollback()
		}
	}()

	if len(updates) > 0 {
		stmt, err := tx.PrepareContext(ctx, `
			INSERT INTO latest_ticks (
				market, ts_code, payload_json, source_api, batch_seq, event_time, received_at, updated_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT(market, ts_code) DO UPDATE SET
				payload_json = excluded.payload_json,
				source_api = excluded.source_api,
				batch_seq = excluded.batch_seq,
				event_time = excluded.event_time,
				received_at = excluded.received_at,
				updated_at = excluded.updated_at
		`)
		if err != nil {
			return 0, 0, err
		}
		for _, update := range updates {
			if _, err := stmt.ExecContext(ctx,
				update.Market,
				update.TSCode,
				update.PayloadJSON,
				update.SourceAPI,
				update.BatchSeq,
				update.EventTime,
				update.ReceivedAt,
				update.UpdatedAt,
			); err != nil {
				_ = stmt.Close()
				return 0, 0, err
			}
		}
		_ = stmt.Close()
	}

	if len(newOffsets) > 0 {
		stmt, err := tx.PrepareContext(ctx, `
			INSERT INTO ingest_offsets (file_path, offset, updated_at)
			VALUES (?, ?, ?)
			ON CONFLICT(file_path) DO UPDATE SET
				offset = excluded.offset,
				updated_at = excluded.updated_at
		`)
		if err != nil {
			return 0, 0, err
		}
		nowISO := utcNowISO()
		for filePath, offset := range newOffsets {
			if _, err := stmt.ExecContext(ctx, filePath, offset, nowISO); err != nil {
				_ = stmt.Close()
				return 0, 0, err
			}
		}
		_ = stmt.Close()
	}

	nowISO := utcNowISO()
	if err := upsertMetaTx(ctx, tx, "last_flush_at", nowISO); err != nil {
		return 0, 0, err
	}
	if err := upsertMetaTx(ctx, tx, "last_flush_items", fmt.Sprintf("%d", processed)); err != nil {
		return 0, 0, err
	}

	if err := tx.Commit(); err != nil {
		return 0, 0, err
	}
	rollback = false

	if s.cfg.SaveCSV && len(touchedMarkets) > 0 {
		s.exportSnapshotCSV(touchedMarkets)
	}

	return processed, len(updates), nil
}

func (s *PushDataStore) readOffset(filePath string) (int64, error) {
	var offset int64
	err := s.db.QueryRow("SELECT offset FROM ingest_offsets WHERE file_path = ?", filePath).Scan(&offset)
	if err == nil {
		return offset, nil
	}
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil
	}
	return 0, err
}

func upsertMetaTx(ctx context.Context, tx *sql.Tx, key, value string) error {
	_, err := tx.ExecContext(ctx, `
		INSERT INTO runtime_meta (key, value, updated_at)
		VALUES (?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET
			value = excluded.value,
			updated_at = excluded.updated_at
	`, key, value, utcNowISO())
	return err
}

func (s *PushDataStore) getMeta(key string) (string, error) {
	var value string
	err := s.db.QueryRow("SELECT value FROM runtime_meta WHERE key = ? LIMIT 1", key).Scan(&value)
	if err == nil {
		return value, nil
	}
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	return "", err
}

func (s *PushDataStore) getLatest(market, tsCode string, limit int) map[string]any {
	if limit < 1 {
		limit = 1
	}
	if limit > 2000 {
		limit = 2000
	}

	var rows *sql.Rows
	var err error
	switch {
	case strings.TrimSpace(tsCode) != "" && strings.TrimSpace(market) != "":
		rows, err = s.db.Query("SELECT market, payload_json FROM latest_ticks WHERE ts_code = ? AND market = ? LIMIT 1", tsCode, market)
	case strings.TrimSpace(tsCode) != "":
		rows, err = s.db.Query("SELECT market, payload_json FROM latest_ticks WHERE ts_code = ? LIMIT 1", tsCode)
	case strings.TrimSpace(market) != "":
		rows, err = s.db.Query("SELECT market, payload_json FROM latest_ticks WHERE market = ? ORDER BY updated_at DESC LIMIT ?", market, limit)
	default:
		rows, err = s.db.Query("SELECT market, payload_json FROM latest_ticks ORDER BY updated_at DESC LIMIT ?", limit)
	}
	if err != nil {
		return map[string]any{"count": 0, "data": []any{}}
	}
	defer rows.Close()

	data := make([]any, 0)
	for rows.Next() {
		var rowMarket, payloadJSON string
		if err := rows.Scan(&rowMarket, &payloadJSON); err != nil {
			continue
		}
		payload := map[string]any{}
		if err := json.Unmarshal([]byte(payloadJSON), &payload); err != nil {
			continue
		}
		if _, ok := payload["market"]; !ok {
			payload["market"] = rowMarket
		}
		data = append(data, payload)
	}
	return map[string]any{"count": len(data), "data": data}
}

func (s *PushDataStore) getStats() map[string]any {
	latestCounts := map[string]int{}
	rows, err := s.db.Query("SELECT market, COUNT(*) AS count FROM latest_ticks GROUP BY market ORDER BY market")
	if err == nil {
		for rows.Next() {
			var market string
			var count int
			if scanErr := rows.Scan(&market, &count); scanErr == nil {
				latestCounts[market] = count
			}
		}
		rows.Close()
	}

	offsetCount := querySingleInt(s.db, "SELECT COUNT(*) FROM ingest_offsets")
	policyCount := querySingleInt(s.db, "SELECT COUNT(*) FROM user_policies")
	subscriptionRows := querySingleInt(s.db, "SELECT COUNT(*) FROM user_subscriptions")
	subscriptionUsers := querySingleInt(s.db, "SELECT COUNT(DISTINCT user_id) FROM user_subscriptions")
	lastFlushAt, _ := s.getMeta("last_flush_at")
	lastFlushItems, _ := s.getMeta("last_flush_items")
	lastCleanupDate, _ := s.getMeta("last_daily_cleanup_date")

	return map[string]any{
		"latest_counts":              latestCounts,
		"offset_files":               offsetCount,
		"policy_count":               policyCount,
		"subscription_rows":          subscriptionRows,
		"subscription_users":         subscriptionUsers,
		"flush_interval_seconds":     s.cfg.FlushIntervalSeconds,
		"last_flush_at":              lastFlushAt,
		"last_flush_items":           mustInt(lastFlushItems),
		"last_daily_cleanup_date":    lastCleanupDate,
		"daily_cleanup_timezone":     s.cfg.Timezone,
		"daily_cleanup_trigger_hour": 9,
	}
}

func (s *PushDataStore) applyPolicies(payload map[string]any) int {
	users, ok := payload["users"].([]any)
	if !ok {
		return 0
	}
	ctx := context.Background()
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return 0
	}
	rollback := true
	defer func() {
		if rollback {
			_ = tx.Rollback()
		}
	}()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO user_policies (user_id, payload_json, revision, updated_at)
		VALUES (?, ?, ?, ?)
		ON CONFLICT(user_id) DO UPDATE SET
			payload_json = excluded.payload_json,
			revision = excluded.revision,
			updated_at = excluded.updated_at
	`)
	if err != nil {
		return 0
	}
	defer stmt.Close()

	applied := 0
	nowISO := utcNowISO()
	for _, rawItem := range users {
		item, ok := rawItem.(map[string]any)
		if !ok {
			continue
		}
		userID := strings.TrimSpace(asString(item["user_id"]))
		if userID == "" {
			continue
		}
		payloadJSON, err := json.Marshal(item)
		if err != nil {
			continue
		}
		revision := mustInt(item["revision"])
		if _, err := stmt.ExecContext(ctx, userID, string(payloadJSON), revision, nowISO); err != nil {
			continue
		}
		applied++
	}

	if err := tx.Commit(); err != nil {
		return 0
	}
	rollback = false
	return applied
}

func (s *PushDataStore) getPolicy(userID string) (map[string]any, error) {
	var payloadJSON string
	err := s.db.QueryRow("SELECT payload_json FROM user_policies WHERE user_id = ? LIMIT 1", userID).Scan(&payloadJSON)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	payload := map[string]any{}
	if err := json.Unmarshal([]byte(payloadJSON), &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func (s *PushDataStore) getUserSubscriptions(userID string) ([]string, error) {
	rows, err := s.db.Query("SELECT ts_code FROM user_subscriptions WHERE user_id = ? ORDER BY updated_at, ts_code", userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make([]string, 0)
	for rows.Next() {
		var tsCode string
		if err := rows.Scan(&tsCode); err == nil && strings.TrimSpace(tsCode) != "" {
			result = append(result, strings.ToUpper(strings.TrimSpace(tsCode)))
		}
	}
	return result, nil
}

func (s *PushDataStore) replaceUserSubscriptions(userID string, symbols []string) error {
	ctx := context.Background()
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	rollback := true
	defer func() {
		if rollback {
			_ = tx.Rollback()
		}
	}()

	if _, err := tx.ExecContext(ctx, "DELETE FROM user_subscriptions WHERE user_id = ?", userID); err != nil {
		return err
	}
	if len(symbols) > 0 {
		stmt, err := tx.PrepareContext(ctx, "INSERT INTO user_subscriptions (user_id, ts_code, updated_at) VALUES (?, ?, ?)")
		if err != nil {
			return err
		}
		nowISO := utcNowISO()
		for _, symbol := range symbols {
			if _, err := stmt.ExecContext(ctx, userID, symbol, nowISO); err != nil {
				_ = stmt.Close()
				return err
			}
		}
		_ = stmt.Close()
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	rollback = false
	return nil
}

func (s *PushDataStore) syncUserSubscriptions(userID string, rawSymbols []any, scope EffectiveScope, mode string) map[string]any {
	currentSymbols, _ := s.getUserSubscriptions(userID)
	currentSet := map[string]struct{}{}
	for _, symbol := range currentSymbols {
		currentSet[symbol] = struct{}{}
	}

	normalizedSymbols, invalid := parseSymbolItems(rawSymbols)
	candidateSymbols := make([]string, 0)
	switch mode {
	case "add":
		candidateSymbols = append(candidateSymbols, currentSymbols...)
		for _, symbol := range normalizedSymbols {
			if _, ok := currentSet[symbol]; ok {
				continue
			}
			candidateSymbols = append(candidateSymbols, symbol)
			currentSet[symbol] = struct{}{}
		}
	case "remove":
		removeSet := map[string]struct{}{}
		for _, symbol := range normalizedSymbols {
			removeSet[symbol] = struct{}{}
		}
		for _, symbol := range currentSymbols {
			if _, shouldRemove := removeSet[symbol]; !shouldRemove {
				candidateSymbols = append(candidateSymbols, symbol)
			}
		}
	default:
		candidateSymbols = normalizedSymbols
	}

	acceptedSymbols, rejectedSymbols := validateSubscriptionSymbols(candidateSymbols, scope)
	rejectedSymbols = append(invalid, rejectedSymbols...)
	_ = s.replaceUserSubscriptions(userID, acceptedSymbols)

	return map[string]any{
		"user_id":               userID,
		"mode":                  mode,
		"accepted_symbols":      acceptedSymbols,
		"rejected_symbols":      rejectedSymbols,
		"current_subscriptions": len(acceptedSymbols),
		"max_subs":              scope.MaxSubs,
		"revision":              scope.Revision,
	}
}

func (s *PushDataStore) getSubscriptionSnapshot(symbols []string, stepSeconds int) map[string]any {
	orderedSymbols := make([]string, 0, len(symbols))
	seen := map[string]struct{}{}
	for _, symbol := range symbols {
		if _, ok := seen[symbol]; ok {
			continue
		}
		seen[symbol] = struct{}{}
		orderedSymbols = append(orderedSymbols, symbol)
	}

	payloads := map[string]map[string]any{}
	for start := 0; start < len(orderedSymbols); start += 200 {
		end := start + 200
		if end > len(orderedSymbols) {
			end = len(orderedSymbols)
		}
		chunk := orderedSymbols[start:end]
		query := fmt.Sprintf("SELECT market, ts_code, payload_json FROM latest_ticks WHERE ts_code IN (%s)", buildPlaceholders(len(chunk)))
		args := make([]any, 0, len(chunk))
		for _, symbol := range chunk {
			args = append(args, symbol)
		}
		rows, err := s.db.Query(query, args...)
		if err != nil {
			continue
		}
		for rows.Next() {
			var market, tsCode, payloadJSON string
			if err := rows.Scan(&market, &tsCode, &payloadJSON); err != nil {
				continue
			}
			payload := map[string]any{}
			if err := json.Unmarshal([]byte(payloadJSON), &payload); err != nil {
				continue
			}
			payload["market"] = market
			payload["ts_code"] = tsCode
			payloads[tsCode] = payload
		}
		rows.Close()
	}

	data := make([]any, 0, len(orderedSymbols))
	missing := make([]string, 0)
	for _, symbol := range orderedSymbols {
		if payload, ok := payloads[symbol]; ok {
			data = append(data, payload)
		} else {
			missing = append(missing, symbol)
		}
	}
	return map[string]any{
		"count":        len(data),
		"step_seconds": stepSeconds,
		"data":         data,
		"missing":      missing,
	}
}

func (s *PushDataStore) exportSnapshotCSV(markets map[string]struct{}) {
	for market := range markets {
		rows, err := s.db.Query("SELECT payload_json FROM latest_ticks WHERE market = ? ORDER BY ts_code", market)
		if err != nil {
			continue
		}

		payloads := make([]map[string]any, 0)
		headers := make([]string, 0)
		seen := map[string]struct{}{}
		for rows.Next() {
			var payloadJSON string
			if err := rows.Scan(&payloadJSON); err != nil {
				continue
			}
			payload := map[string]any{}
			if err := json.Unmarshal([]byte(payloadJSON), &payload); err != nil {
				continue
			}
			payloads = append(payloads, payload)
			for key := range payload {
				if _, ok := seen[key]; ok {
					continue
				}
				seen[key] = struct{}{}
				headers = append(headers, key)
			}
		}
		rows.Close()
		if len(payloads) == 0 {
			continue
		}
		sort.Strings(headers)

		tmpPath := filepath.Join(s.snapshotDir, market+"_latest.csv.tmp")
		finalPath := filepath.Join(s.snapshotDir, market+"_latest.csv")
		file, err := os.Create(tmpPath)
		if err != nil {
			continue
		}
		writer := csv.NewWriter(file)
		_ = writer.Write(headers)
		for _, payload := range payloads {
			row := make([]string, 0, len(headers))
			for _, header := range headers {
				row = append(row, asString(payload[header]))
			}
			_ = writer.Write(row)
		}
		writer.Flush()
		_ = file.Close()
		if writer.Error() == nil {
			_ = os.Rename(tmpPath, finalPath)
		}
	}
}

func (s *PushDataStore) removeSnapshotCSVs() error {
	matches, err := filepath.Glob(filepath.Join(s.snapshotDir, "*.csv"))
	if err != nil {
		return err
	}
	for _, match := range matches {
		if err := os.Remove(match); err != nil && !errors.Is(err, os.ErrNotExist) {
			return err
		}
	}
	return nil
}

func (s *PushDataStore) cleanupEmptySpoolDirs() {
	entries, err := os.ReadDir(s.spoolDir)
	if err != nil {
		return
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		marketDir := filepath.Join(s.spoolDir, entry.Name())
		subEntries, err := os.ReadDir(marketDir)
		if err == nil && len(subEntries) == 0 {
			_ = os.Remove(marketDir)
		}
	}
}

func buildPlaceholders(n int) string {
	placeholders := make([]string, 0, n)
	for i := 0; i < n; i++ {
		placeholders = append(placeholders, "?")
	}
	return strings.Join(placeholders, ",")
}

func querySingleInt(db *sql.DB, query string, args ...any) int {
	var value int
	if err := db.QueryRow(query, args...).Scan(&value); err != nil {
		return 0
	}
	return value
}

func bytesTrimSpace(b []byte) []byte {
	return []byte(strings.TrimSpace(string(b)))
}
