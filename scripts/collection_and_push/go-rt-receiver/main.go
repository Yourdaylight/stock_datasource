package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func main() {
	cfg := ParseConfig()

	store, err := NewPushDataStore(cfg)
	if err != nil {
		log.Fatalf("[FATAL] init store: %v", err)
	}

	// ── WebSocket Hub ───────────────────────────────────────────
	wsHub := NewWSHub(cfg, store)
	store.wsHub = wsHub
	wsHub.Start()

	store.StartBuilder()

	mux := http.NewServeMux()

	// ── Routes ───────────────────────────────────────────────────
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		writeJSON(w, 200, map[string]any{
			"service": "push-data-receiver",
			"version": "3.1.0-go",
			"storage": map[string]any{
				"spool_dir":              store.spoolDir,
				"sqlite_path":           store.dbPath,
				"flush_interval_seconds": cfg.FlushIntervalSeconds,
				"flush_max_items":        cfg.FlushMaxItems,
			},
			"websocket": map[string]any{
				"endpoint":    "ws://<host>:<port>/ws",
				"description": "实时行情 WebSocket 推送，采集端数据到达后直接推送",
				"auth":        "可选，?token=<jwt> 或 Authorization: Bearer <jwt>",
			},
			"endpoints": map[string]string{
				"GET  /ws":                                   "WebSocket 实时行情推送（subscribe/unsubscribe/snapshot/list）",
				"POST /api/v1/rt-kline/push":                "接收推送数据并追加写入 spool",
				"POST /api/v1/rt-kline/policies/apply":      "接收实时订阅 policy 快照",
				"POST /api/v1/rt-kline/subscription/sync":   "按 JWT + policy 同步当前用户的批量订阅清单",
				"GET  /api/v1/rt-kline/subscription/list":   "查看当前用户已登记的订阅 symbols",
				"GET  /api/v1/rt-kline/latest":              "从 SQLite 快照查询最新行情",
				"GET  /api/v1/rt-kline/subscription/latest": "按 JWT + 已登记订阅查询最新快照",
				"GET  /stats":                               "查看 spool / SQLite 刷盘状态",
				"GET  /health":                              "健康检查",
			},
		})
	})

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"status": "ok", "timestamp": utcNowISO()})
	})

	mux.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
		stats := store.getStats()
		stats["ws_clients"] = wsHub.ClientCount()
		writeJSON(w, 200, stats)
	})

	// ── WebSocket 端点 ─────────────────────────────────────────
	mux.HandleFunc("/ws", wsHub.HandleWebSocket)

	mux.HandleFunc("/api/v1/rt-kline/push", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		// Auth: push token
		if expectedToken := cfg.PushToken; expectedToken != "" {
			bearer := extractBearer(r)
			if bearer == "" {
				writeJSON(w, 401, map[string]any{"status": "error", "code": 401, "message": "missing Authorization header"})
				return
			}
			if bearer != expectedToken {
				writeJSON(w, 403, map[string]any{"status": "error", "code": 403, "message": "invalid push token"})
				return
			}
		}

		payload, err := readJSONBody(r)
		if err != nil || payload == nil {
			writeJSON(w, 400, map[string]any{
				"status": "error", "code": 400,
				"ack_seq": 0, "accepted_count": 0, "rejected_count": 0,
			})
			return
		}

		if vErr := validatePayload(payload); vErr != nil {
			log.Printf("[WARN] invalid payload: %v", vErr)
			writeJSON(w, 400, map[string]any{
				"status":         "error",
				"code":           400,
				"message":        vErr.Error(),
				"ack_seq":        payload["batch_seq"],
				"accepted_count": 0,
				"rejected_count": payload["count"],
			})
			return
		}

		ack := store.StoreBatch(payload)
		log.Printf("[INFO] received market=%s batch_seq=%v count=%v accepted=%v rejected=%v",
			payload["market"], payload["batch_seq"], payload["count"],
			ack["accepted_count"], ack["rejected_count"])
		writeJSON(w, 200, ack)
	})

	mux.HandleFunc("/api/v1/rt-kline/latest", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		market := r.URL.Query().Get("market")
		tsCode := r.URL.Query().Get("ts_code")
		limitStr := r.URL.Query().Get("limit")
		limit := 100
		if limitStr != "" {
			if n, err := strconv.Atoi(limitStr); err == nil {
				limit = n
			}
		}
		writeJSON(w, 200, store.getLatest(market, tsCode, limit))
	})

	mux.HandleFunc("/api/v1/rt-kline/policies/apply", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		// Auth: policy token
		if cfg.PolicyToken != "" {
			bearer := extractBearer(r)
			if bearer == "" {
				writeJSON(w, 401, map[string]any{"status": "error", "code": 401, "message": "missing Authorization header"})
				return
			}
			if bearer != cfg.PolicyToken {
				writeJSON(w, 403, map[string]any{"status": "error", "code": 403, "message": "invalid policy token"})
				return
			}
		}

		payload, err := readJSONBody(r)
		if err != nil || payload == nil {
			writeJSON(w, 400, map[string]any{"status": "error", "code": 400, "message": "payload must be a JSON object"})
			return
		}
		applied := store.applyPolicies(payload)
		writeJSON(w, 200, map[string]any{"status": "ok", "code": 0, "applied": applied})
	})

	mux.HandleFunc("/api/v1/rt-kline/subscription/sync", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		userID, scope, authErr := authenticateSubscriptionRequest(r, cfg, store)
		if authErr != nil {
			code := 401
			if strings.Contains(authErr.Error(), "not configured") {
				code = 500
			}
			writeJSON(w, code, map[string]any{"status": "error", "code": code, "message": authErr.Error()})
			return
		}

		payload, err := readJSONBody(r)
		if err != nil || payload == nil {
			writeJSON(w, 400, map[string]any{"status": "error", "code": 400, "message": "payload must be a JSON object"})
			return
		}

		mode := strings.ToLower(strings.TrimSpace(defaultString(payload["mode"], "replace")))
		if mode != "replace" && mode != "add" && mode != "remove" {
			writeJSON(w, 400, map[string]any{"status": "error", "code": 400, "message": "mode must be replace, add, or remove"})
			return
		}

		rawSymbols, _ := payload["symbols"].([]any)
		if rawSymbols == nil {
			writeJSON(w, 400, map[string]any{"status": "error", "code": 400, "message": "symbols must be an array"})
			return
		}

		result := store.syncUserSubscriptions(userID, rawSymbols, scope, mode)
		result["status"] = "ok"
		result["code"] = 0
		writeJSON(w, 200, result)
	})

	mux.HandleFunc("/api/v1/rt-kline/subscription/list", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		userID, scope, authErr := authenticateSubscriptionRequest(r, cfg, store)
		if authErr != nil {
			code := 401
			if strings.Contains(authErr.Error(), "not configured") {
				code = 500
			}
			writeJSON(w, code, map[string]any{"status": "error", "code": code, "message": authErr.Error()})
			return
		}

		storedSymbols, _ := store.getUserSubscriptions(userID)
		effectiveSymbols, rejected := validateSubscriptionSymbols(storedSymbols, scope)
		writeJSON(w, 200, map[string]any{
			"status":                "ok",
			"code":                  0,
			"user_id":               userID,
			"revision":              scope.Revision,
			"max_subs":              scope.MaxSubs,
			"stored_count":          len(storedSymbols),
			"current_subscriptions": len(effectiveSymbols),
			"subscribed_symbols":    effectiveSymbols,
			"rejected_symbols":      rejected,
		})
	})

	mux.HandleFunc("/api/v1/rt-kline/subscription/latest", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSON(w, 405, map[string]any{"status": "error", "code": 405, "message": "method not allowed"})
			return
		}
		userID, scope, authErr := authenticateSubscriptionRequest(r, cfg, store)
		if authErr != nil {
			code := 401
			if strings.Contains(authErr.Error(), "not configured") {
				code = 500
			}
			writeJSON(w, code, map[string]any{"status": "error", "code": code, "message": authErr.Error()})
			return
		}

		storedSymbols, _ := store.getUserSubscriptions(userID)
		requestedRaw := strings.TrimSpace(r.URL.Query().Get("symbols"))

		var symbols []string
		rejected := make([]map[string]string, 0)

		if requestedRaw != "" {
			requestedSymbols, parseErr := parseSymbolList(requestedRaw)
			if parseErr != nil {
				writeJSON(w, 400, map[string]any{"status": "error", "code": 400, "message": parseErr.Error()})
				return
			}
			storedSet := map[string]struct{}{}
			for _, s := range storedSymbols {
				storedSet[s] = struct{}{}
			}
			for _, symbol := range requestedSymbols {
				if _, ok := storedSet[symbol]; ok {
					symbols = append(symbols, symbol)
				} else {
					rejected = append(rejected, map[string]string{"symbol": symbol, "reason": "not_subscribed"})
				}
			}
		} else {
			symbols = storedSymbols
		}

		allowedSymbols, policyRejected := validateSubscriptionSymbols(symbols, scope)
		rejected = append(rejected, policyRejected...)
		result := store.getSubscriptionSnapshot(allowedSymbols, cfg.SubscriptionStepSeconds)
		result["status"] = "ok"
		result["code"] = 0
		result["user_id"] = userID
		result["revision"] = scope.Revision
		result["max_subs"] = scope.MaxSubs
		result["registered_symbols"] = storedSymbols
		result["accepted_symbols"] = allowedSymbols
		result["rejected_symbols"] = rejected
		writeJSON(w, 200, result)
	})

	// ── Start server ─────────────────────────────────────────────
	srv := &http.Server{
		Addr:         cfg.ListenAddr(),
		Handler:      mux,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		fmt.Printf(`
╔══════════════════════════════════════════════════╗
║  Push Data Receiver (Go) + SQLite + WebSocket    ║
╠══════════════════════════════════════════════════╣
║  Listen      : %-27s║
║  WebSocket   : ws://%-22s║
║  Push URL    : /api/v1/rt-kline/push             ║
║  Policy API  : /api/v1/rt-kline/policies/apply   ║
║  Skills API  : /api/v1/rt-kline/subscription/*   ║
║  Data Dir    : %-31s║
║  Flush Every : %-31s║
╚══════════════════════════════════════════════════╝
`, cfg.ListenAddr(), cfg.ListenAddr()+"/ws", cfg.DataDir, fmt.Sprintf("%ds", cfg.FlushIntervalSeconds))

		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[FATAL] server: %v", err)
		}
	}()

	// ── Graceful shutdown ────────────────────────────────────────
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Printf("[INFO] received signal %v, shutting down...", sig)

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("[ERROR] server shutdown: %v", err)
	}
	wsHub.Stop()
	store.Stop()
	log.Println("[INFO] server stopped")
}

// ── Helpers ──────────────────────────────────────────────────────

func authenticateSubscriptionRequest(r *http.Request, cfg ReceiverConfig, store *PushDataStore) (string, EffectiveScope, error) {
	bearer := extractBearer(r)
	if cfg.JWTPublicKeyPath == "" {
		return "", EffectiveScope{}, fmt.Errorf("jwt_public_key_path is not configured")
	}

	claims, err := verifySubscriptionToken(bearer, cfg.JWTPublicKeyPath)
	if err != nil {
		return "", EffectiveScope{}, err
	}

	userID := strings.TrimSpace(defaultString(claims["sub"], asString(claims["username"])))
	if userID == "" {
		return "", EffectiveScope{}, fmt.Errorf("token missing subject")
	}

	policy, _ := store.getPolicy(userID)
	scope := buildEffectiveSubscriptionScope(claims, policy)
	return userID, scope, nil
}

func extractBearer(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "Bearer ") {
		return strings.TrimSpace(auth[7:])
	}
	return strings.TrimSpace(auth)
}

func readJSONBody(r *http.Request) (map[string]any, error) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 50*1024*1024)) // 50 MB limit
	if err != nil {
		return nil, err
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(data)
}
