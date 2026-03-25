package main

import (
	"encoding/json"
	"log"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// ── WebSocket Hub ──────────────────────────────────────────────

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 4096,
	CheckOrigin: func(r *http.Request) bool {
		return true // 允许所有来源
	},
}

// wsClient 表示一个 WebSocket 连接的客户端
type wsClient struct {
	hub     *WSHub
	conn    *websocket.Conn
	send    chan []byte
	symbols map[string]struct{} // 该客户端订阅的 symbol 集合（空表示接收全部）
	userID  string              // JWT 鉴权后的用户 ID（空表示匿名）
	mu      sync.RWMutex
}

// WSHub 管理所有 WebSocket 连接和广播
type WSHub struct {
	cfg       ReceiverConfig
	store     *PushDataStore
	clients   map[*wsClient]struct{}
	mu        sync.RWMutex
	broadcast chan []tickBroadcast
	stopCh    chan struct{}
}

// tickBroadcast 表示一条需要广播的 tick 数据
type tickBroadcast struct {
	Market      string         `json:"market"`
	TSCode      string         `json:"ts_code"`
	PayloadJSON map[string]any `json:"payload"`
	BatchSeq    int            `json:"batch_seq"`
	EventTime   string         `json:"event_time"`
	SourceAPI   string         `json:"source_api"`
	ReceivedAt  string         `json:"received_at"`
}

func NewWSHub(cfg ReceiverConfig, store *PushDataStore) *WSHub {
	return &WSHub{
		cfg:       cfg,
		store:     store,
		clients:   make(map[*wsClient]struct{}),
		broadcast: make(chan []tickBroadcast, 256),
		stopCh:    make(chan struct{}),
	}
}

func (h *WSHub) Start() {
	go h.broadcastLoop()
}

func (h *WSHub) Stop() {
	close(h.stopCh)
	h.mu.Lock()
	defer h.mu.Unlock()
	for client := range h.clients {
		close(client.send)
		_ = client.conn.Close()
	}
	h.clients = make(map[*wsClient]struct{})
}

func (h *WSHub) broadcastLoop() {
	for {
		select {
		case <-h.stopCh:
			return
		case ticks := <-h.broadcast:
			h.doBroadcast(ticks)
		}
	}
}

// BroadcastTicks 从外部（StoreBatch）调用，将 tick 数据排入广播队列
func (h *WSHub) BroadcastTicks(ticks []tickBroadcast) {
	if len(ticks) == 0 {
		return
	}
	select {
	case h.broadcast <- ticks:
	default:
		// 队列满则丢弃，防止阻塞采集端
		log.Printf("[WARN] websocket broadcast queue full, dropping %d ticks", len(ticks))
	}
}

func (h *WSHub) doBroadcast(ticks []tickBroadcast) {
	h.mu.RLock()
	clients := make([]*wsClient, 0, len(h.clients))
	for c := range h.clients {
		clients = append(clients, c)
	}
	h.mu.RUnlock()

	if len(clients) == 0 {
		return
	}

	for _, tick := range ticks {
		msg := map[string]any{
			"type":      "tick",
			"timestamp": utcNowISO(),
			"ts_code":   tick.TSCode,
			"market":    tick.Market,
			"batch_seq": tick.BatchSeq,
		}
		// 将 payload 字段展开到顶层
		for k, v := range tick.PayloadJSON {
			if k != "type" && k != "timestamp" {
				msg[k] = v
			}
		}

		data, err := json.Marshal(msg)
		if err != nil {
			continue
		}

		for _, client := range clients {
			if client.shouldReceive(tick.TSCode) {
				select {
				case client.send <- data:
				default:
					// 客户端 send buffer 满，关闭连接
					h.removeClient(client)
				}
			}
		}
	}
}

func (h *WSHub) addClient(client *wsClient) {
	h.mu.Lock()
	h.clients[client] = struct{}{}
	count := len(h.clients)
	h.mu.Unlock()
	log.Printf("[INFO] ws client connected, total=%d", count)
}

func (h *WSHub) removeClient(client *wsClient) {
	h.mu.Lock()
	if _, ok := h.clients[client]; ok {
		delete(h.clients, client)
		close(client.send)
		_ = client.conn.Close()
	}
	count := len(h.clients)
	h.mu.Unlock()
	log.Printf("[INFO] ws client disconnected, total=%d", count)
}

func (h *WSHub) ClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

// ── Client methods ─────────────────────────────────────────────

func (c *wsClient) shouldReceive(tsCode string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if len(c.symbols) == 0 {
		return true // 没指定 symbol 列表则接收全部
	}
	_, ok := c.symbols[tsCode]
	return ok
}

func (c *wsClient) getSymbols() []string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	result := make([]string, 0, len(c.symbols))
	for s := range c.symbols {
		result = append(result, s)
	}
	sort.Strings(result)
	return result
}

func (c *wsClient) addSymbols(symbols []string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, s := range symbols {
		s = strings.ToUpper(strings.TrimSpace(s))
		if s != "" && strings.Contains(s, ".") {
			c.symbols[s] = struct{}{}
		}
	}
}

func (c *wsClient) removeSymbols(symbols []string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, s := range symbols {
		s = strings.ToUpper(strings.TrimSpace(s))
		delete(c.symbols, s)
	}
}

// ── WebSocket HTTP Handler ─────────────────────────────────────

func (h *WSHub) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[ERROR] ws upgrade failed: %v", err)
		return
	}

	// 可选 JWT 鉴权：从 query 参数 ?token=xxx 或 Sec-WebSocket-Protocol 中获取
	var userID string
	tokenStr := r.URL.Query().Get("token")
	if tokenStr == "" {
		tokenStr = extractBearer(r)
	}
	if tokenStr != "" && h.cfg.JWTPublicKeyPath != "" {
		claims, err := verifySubscriptionToken(tokenStr, h.cfg.JWTPublicKeyPath)
		if err != nil {
			log.Printf("[WARN] ws auth failed: %v", err)
			// 鉴权失败不阻止连接，但标记为匿名
		} else {
			userID = strings.TrimSpace(defaultString(claims["sub"], asString(claims["username"])))
		}
	}

	client := &wsClient{
		hub:     h,
		conn:    conn,
		send:    make(chan []byte, 256),
		symbols: make(map[string]struct{}),
		userID:  userID,
	}

	h.addClient(client)

	// 发送欢迎消息
	welcome := map[string]any{
		"type":      "welcome",
		"message":   "实时行情 WebSocket 已连接",
		"user_id":   userID,
		"timestamp": utcNowISO(),
		"instructions": map[string]string{
			"subscribe":   `发送 {"action":"subscribe","symbols":["00700.HK"]} 订阅`,
			"unsubscribe": `发送 {"action":"unsubscribe","symbols":["00700.HK"]} 取消订阅`,
			"snapshot":    `发送 {"action":"snapshot"} 获取当前所有最新行情`,
			"list":        `发送 {"action":"list"} 查看当前订阅列表`,
		},
	}
	if data, err := json.Marshal(welcome); err == nil {
		select {
		case client.send <- data:
		default:
		}
	}

	// 如果是已认证用户，自动加载服务端已登记的订阅
	if userID != "" {
		storedSymbols, err := h.store.getUserSubscriptions(userID)
		if err == nil && len(storedSymbols) > 0 {
			client.addSymbols(storedSymbols)
			autoSubMsg := map[string]any{
				"type":      "auto_subscribed",
				"message":   "已自动加载服务端已登记的订阅",
				"symbols":   storedSymbols,
				"timestamp": utcNowISO(),
			}
			if data, err := json.Marshal(autoSubMsg); err == nil {
				select {
				case client.send <- data:
				default:
				}
			}
		}
	}

	// 启动读写 goroutine
	go client.writePump()
	go client.readPump()
}

// writePump 将 send channel 中的消息写入 WebSocket 连接
func (c *wsClient) writePump() {
	ticker := time.NewTicker(30 * time.Second) // ping 间隔
	defer func() {
		ticker.Stop()
		c.hub.removeClient(c)
	}()

	for {
		select {
		case msg, ok := <-c.send:
			if !ok {
				// channel 已关闭
				_ = c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			_ = c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		case <-ticker.C:
			_ = c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// readPump 从 WebSocket 连接读取客户端消息（订阅管理指令）
func (c *wsClient) readPump() {
	defer func() {
		c.hub.removeClient(c)
	}()

	c.conn.SetReadLimit(64 * 1024) // 64KB
	_ = c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		_ = c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseNormalClosure) {
				log.Printf("[WARN] ws read error: %v", err)
			}
			return
		}

		// 重置读超时
		_ = c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))

		var msg map[string]any
		if err := json.Unmarshal(message, &msg); err != nil {
			resp := map[string]any{
				"type":    "error",
				"message": "无效 JSON 格式",
			}
			if data, err := json.Marshal(resp); err == nil {
				select {
				case c.send <- data:
				default:
				}
			}
			continue
		}

		c.handleMessage(msg)
	}
}

func (c *wsClient) handleMessage(msg map[string]any) {
	action := strings.ToLower(strings.TrimSpace(asString(msg["action"])))

	switch action {
	case "subscribe":
		c.handleSubscribe(msg)
	case "unsubscribe":
		c.handleUnsubscribe(msg)
	case "snapshot":
		c.handleSnapshot()
	case "list":
		c.handleList()
	default:
		resp := map[string]any{
			"type":    "error",
			"message": "未知 action: " + action + "，支持 subscribe/unsubscribe/snapshot/list",
		}
		if data, err := json.Marshal(resp); err == nil {
			select {
			case c.send <- data:
			default:
			}
		}
	}
}

func (c *wsClient) handleSubscribe(msg map[string]any) {
	rawSymbols, _ := msg["symbols"].([]any)
	newSymbols := make([]string, 0, len(rawSymbols))
	for _, raw := range rawSymbols {
		s := strings.ToUpper(strings.TrimSpace(asString(raw)))
		if s != "" && strings.Contains(s, ".") {
			newSymbols = append(newSymbols, s)
		}
	}

	if len(newSymbols) == 0 {
		resp := map[string]any{
			"type":    "error",
			"message": "symbols 不能为空",
		}
		if data, err := json.Marshal(resp); err == nil {
			select {
			case c.send <- data:
			default:
			}
		}
		return
	}

	c.addSymbols(newSymbols)

	// 如果是已认证用户，同步到服务端订阅表
	serverSync := "skipped"
	if c.userID != "" {
		scope, err := c.getUserScope()
		if err == nil {
			anySymbols := make([]any, len(newSymbols))
			for i, s := range newSymbols {
				anySymbols[i] = s
			}
			result := c.hub.store.syncUserSubscriptions(c.userID, anySymbols, scope, "add")
			if result["accepted_symbols"] != nil {
				serverSync = "ok"
			}
		} else {
			serverSync = "auth_error"
		}
	}

	resp := map[string]any{
		"type":        "subscribed",
		"added":       newSymbols,
		"current":     c.getSymbols(),
		"server_sync": serverSync,
		"timestamp":   utcNowISO(),
	}
	if data, err := json.Marshal(resp); err == nil {
		select {
		case c.send <- data:
		default:
		}
	}
}

func (c *wsClient) handleUnsubscribe(msg map[string]any) {
	rawSymbols, _ := msg["symbols"].([]any)
	rmSymbols := make([]string, 0, len(rawSymbols))
	for _, raw := range rawSymbols {
		s := strings.ToUpper(strings.TrimSpace(asString(raw)))
		if s != "" {
			rmSymbols = append(rmSymbols, s)
		}
	}

	c.removeSymbols(rmSymbols)

	// 如果是已认证用户，同步退订到服务端
	serverSync := "skipped"
	if c.userID != "" {
		scope, err := c.getUserScope()
		if err == nil {
			anySymbols := make([]any, len(rmSymbols))
			for i, s := range rmSymbols {
				anySymbols[i] = s
			}
			result := c.hub.store.syncUserSubscriptions(c.userID, anySymbols, scope, "remove")
			if result["accepted_symbols"] != nil {
				serverSync = "ok"
			}
		} else {
			serverSync = "auth_error"
		}
	}

	resp := map[string]any{
		"type":        "unsubscribed",
		"removed":     rmSymbols,
		"current":     c.getSymbols(),
		"server_sync": serverSync,
		"timestamp":   utcNowISO(),
	}
	if data, err := json.Marshal(resp); err == nil {
		select {
		case c.send <- data:
		default:
		}
	}
}

func (c *wsClient) handleSnapshot() {
	symbols := c.getSymbols()
	var data []any

	if len(symbols) > 0 {
		result := c.hub.store.getSubscriptionSnapshot(symbols, c.hub.cfg.SubscriptionStepSeconds)
		data, _ = result["data"].([]any)
	} else {
		result := c.hub.store.getLatest("", "", 2000)
		data, _ = result["data"].([]any)
	}

	if data == nil {
		data = make([]any, 0)
	}

	resp := map[string]any{
		"type":      "snapshot",
		"count":     len(data),
		"data":      data,
		"timestamp": utcNowISO(),
	}
	if respData, err := json.Marshal(resp); err == nil {
		select {
		case c.send <- respData:
		default:
		}
	}
}

func (c *wsClient) handleList() {
	resp := map[string]any{
		"type":      "subscription_list",
		"symbols":   c.getSymbols(),
		"user_id":   c.userID,
		"timestamp": utcNowISO(),
	}
	if data, err := json.Marshal(resp); err == nil {
		select {
		case c.send <- data:
		default:
		}
	}
}

// getUserScope 获取当前用户的有效订阅范围（仅已认证用户）
func (c *wsClient) getUserScope() (EffectiveScope, error) {
	if c.userID == "" {
		return EffectiveScope{}, nil
	}
	// 简化处理：无 policy 限制时返回宽松 scope
	policy, _ := c.hub.store.getPolicy(c.userID)
	// 构造一个基础 claims（由于 WebSocket 鉴权只做一次，后续操作复用 userID）
	fakeClaims := map[string]any{
		"sub": c.userID,
	}
	scope := buildEffectiveSubscriptionScope(fakeClaims, policy)
	return scope, nil
}
