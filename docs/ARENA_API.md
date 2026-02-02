# 多Agent策略竞技场 API 文档

## 概述

多Agent策略竞技场API提供了完整的竞技场管理、策略竞争、Agent讨论和评估功能接口。

## 基础URL

```
/api/arena
```

## 认证

所有API端点都需要认证。请在请求头中包含有效的认证token。

---

## 竞技场管理

### 创建竞技场

**POST** `/api/arena/create`

创建一个新的多Agent策略竞技场。

**请求体**

```json
{
  "name": "我的竞技场",
  "description": "测试竞技场描述",
  "agent_count": 5,
  "symbols": ["000001.SZ", "600000.SH"],
  "discussion_max_rounds": 3,
  "initial_capital": 100000.0,
  "backtest_start_date": "2024-01-01",
  "backtest_end_date": "2024-12-31",
  "simulated_duration_days": 30
}
```

**参数说明**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 竞技场名称 |
| description | string | 否 | 竞技场描述 |
| agent_count | int | 否 | Agent数量 (3-10)，默认5 |
| symbols | array | 否 | 股票代码列表 |
| discussion_max_rounds | int | 否 | 最大讨论轮数 (1-10)，默认3 |
| initial_capital | float | 否 | 初始资金，默认100000 |
| backtest_start_date | string | 否 | 回测开始日期 |
| backtest_end_date | string | 否 | 回测结束日期 |
| simulated_duration_days | int | 否 | 模拟交易天数 (1-365)，默认30 |

**响应**

```json
{
  "id": "arena_abc123",
  "name": "我的竞技场",
  "state": "created",
  "active_strategies": 0,
  "total_strategies": 0,
  "eliminated_strategies": 0,
  "discussion_rounds": 0,
  "last_evaluation": null,
  "duration_seconds": 0,
  "error_count": 0,
  "last_error": null
}
```

---

### 获取竞技场状态

**GET** `/api/arena/{arena_id}/status`

获取指定竞技场的当前状态。

**响应**

```json
{
  "id": "arena_abc123",
  "name": "我的竞技场",
  "state": "discussing",
  "active_strategies": 5,
  "total_strategies": 5,
  "eliminated_strategies": 0,
  "discussion_rounds": 2,
  "last_evaluation": "2024-01-15T10:30:00",
  "duration_seconds": 3600.5,
  "error_count": 0,
  "last_error": null
}
```

**状态说明**

| 状态 | 说明 |
|------|------|
| created | 已创建，等待启动 |
| initializing | 初始化中 |
| discussing | 讨论进行中 |
| backtesting | 回测进行中 |
| simulating | 模拟交易中 |
| evaluating | 评估中 |
| paused | 已暂停 |
| completed | 已完成 |
| failed | 失败 |

---

### 启动竞技场

**POST** `/api/arena/{arena_id}/start`

启动竞技场竞争流程。

**响应**

```json
{
  "status": "started",
  "arena_id": "arena_abc123"
}
```

---

### 暂停竞技场

**POST** `/api/arena/{arena_id}/pause`

暂停竞技场竞争流程。

---

### 恢复竞技场

**POST** `/api/arena/{arena_id}/resume`

恢复已暂停的竞技场。

---

### 删除竞技场

**DELETE** `/api/arena/{arena_id}`

删除指定竞技场及其所有数据。

---

### 列出所有竞技场

**GET** `/api/arena/list`

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | string | 否 | 按状态过滤 |
| limit | int | 否 | 返回数量限制 (1-100)，默认50 |

**响应**

```json
{
  "total": 3,
  "arenas": [
    {
      "id": "arena_abc123",
      "name": "竞技场1",
      "state": "discussing",
      "active_strategies": 5
    }
  ]
}
```

---

## 思考流

### SSE实时思考流

**GET** `/api/arena/{arena_id}/thinking-stream`

Server-Sent Events端点，实时获取Agent思考消息。

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| round_id | string | 否 | 按讨论轮次过滤 |

**事件格式**

```
data: {
  "id": "msg_123",
  "arena_id": "arena_abc123",
  "agent_id": "agent_1",
  "agent_role": "strategy_generator",
  "round_id": "round_1",
  "message_type": "thinking",
  "content": "分析市场数据...",
  "metadata": {},
  "timestamp": "2024-01-15T10:30:00"
}
```

**消息类型**

| 类型 | 说明 |
|------|------|
| thinking | 思考过程 |
| argument | 论证观点 |
| conclusion | 结论 |
| intervention | 人工干预 |
| error | 错误 |

---

### 获取讨论历史

**GET** `/api/arena/{arena_id}/discussions`

**响应**

```json
{
  "total": 5,
  "discussions": [
    {
      "id": "round_1",
      "arena_id": "arena_abc123",
      "round_number": 1,
      "mode": "debate",
      "participants": ["agent_1", "agent_2"],
      "conclusions": {
        "agent_1": "建议采用均线策略",
        "agent_2": "建议关注风险控制"
      },
      "started_at": "2024-01-15T10:00:00",
      "completed_at": "2024-01-15T10:30:00",
      "duration_seconds": 1800
    }
  ]
}
```

---

## 策略管理

### 获取策略列表

**GET** `/api/arena/{arena_id}/strategies`

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| active_only | boolean | 否 | 只返回活跃策略，默认false |

---

### 获取策略详情

**GET** `/api/arena/{arena_id}/strategies/{strategy_id}`

**响应**

```json
{
  "id": "strategy_1",
  "name": "均线交叉策略",
  "description": "基于MA5和MA20的交叉信号",
  "agent_id": "agent_1",
  "agent_role": "strategy_generator",
  "stage": "simulated",
  "is_active": true,
  "current_score": 75.5,
  "current_rank": 2,
  "logic": "当MA5上穿MA20时买入...",
  "rules": {
    "buy_condition": "MA5 > MA20",
    "sell_condition": "MA5 < MA20",
    "stop_loss": 0.05,
    "take_profit": 0.10
  }
}
```

---

### 获取排行榜

**GET** `/api/arena/{arena_id}/leaderboard`

**响应**

```json
{
  "total": 5,
  "leaderboard": [
    {
      "rank": 1,
      "strategy_id": "strategy_1",
      "name": "均线交叉策略",
      "agent_id": "agent_1",
      "agent_role": "strategy_generator",
      "score": 85.5,
      "stage": "simulated"
    }
  ]
}
```

---

### 获取策略评分明细

**GET** `/api/arena/{arena_id}/strategies/{strategy_id}/score-breakdown`

**响应**

```json
{
  "strategy_id": "strategy_1",
  "total_score": 75.5,
  "breakdown": {
    "profitability": 80.0,
    "risk_control": 70.0,
    "stability": 75.0,
    "adaptability": 72.0
  },
  "weights": {
    "profitability": 0.30,
    "risk_control": 0.30,
    "stability": 0.20,
    "adaptability": 0.20
  }
}
```

---

## 评估与淘汰

### 触发评估

**POST** `/api/arena/{arena_id}/evaluate`

手动触发周期评估。

**请求体**

```json
{
  "period": "weekly"
}
```

| period值 | 说明 | 淘汰率 |
|----------|------|--------|
| daily | 日评 | 不淘汰 |
| weekly | 周评 | 末位20% |
| monthly | 月评 | 末位10% |

---

### 获取淘汰历史

**GET** `/api/arena/{arena_id}/elimination-history`

**响应**

```json
{
  "total": 3,
  "events": [
    {
      "id": "elim_strategy_3",
      "type": "elimination",
      "timestamp": "2024-01-15T10:30:00",
      "period": "weekly",
      "strategy_name": "高频交易策略",
      "strategy_id": "strategy_3",
      "score": 45.2,
      "reason": "评分低于淘汰阈值"
    },
    {
      "id": "eval_123",
      "type": "evaluation",
      "timestamp": "2024-01-15T10:00:00",
      "period": "weekly",
      "total_strategies": 5,
      "eliminated_count": 1
    }
  ]
}
```

---

## 讨论控制

### 触发讨论

**POST** `/api/arena/{arena_id}/discussion/start`

**请求体**

```json
{
  "mode": "debate"
}
```

| mode值 | 说明 |
|--------|------|
| debate | 辩论模式 - Agent之间相互辩论策略优劣 |
| collaboration | 协作模式 - Agent协作优化策略 |
| review | 评审模式 - Agent评审其他Agent的策略 |

---

### 获取当前讨论状态

**GET** `/api/arena/{arena_id}/discussion/current`

---

### 人工干预

**POST** `/api/arena/{arena_id}/discussion/intervention`

允许人工干预竞技场运行。

**请求体**

```json
{
  "action": "inject_message",
  "message": "请关注近期市场波动风险",
  "reason": "市场环境变化"
}
```

**可用操作**

| action值 | 说明 | 必需参数 |
|----------|------|----------|
| inject_message | 注入消息到讨论 | message |
| adjust_score | 调整策略评分 | target_strategy_id, score_adjustment (-50 to +50) |
| eliminate_strategy | 强制淘汰策略 | target_strategy_id |
| add_strategy | 添加新策略 | new_strategy_config |

**示例 - 调整评分**

```json
{
  "action": "adjust_score",
  "target_strategy_id": "strategy_1",
  "score_adjustment": 10,
  "reason": "手动奖励优秀表现"
}
```

**示例 - 强制淘汰**

```json
{
  "action": "eliminate_strategy",
  "target_strategy_id": "strategy_3",
  "reason": "策略逻辑存在严重问题"
}
```

---

## 错误响应

所有API在发生错误时返回以下格式：

```json
{
  "detail": "错误描述信息"
}
```

**常见HTTP状态码**

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## WebSocket支持

思考流同时支持WebSocket连接（开发中）：

```
ws://localhost:8000/ws/arena/{arena_id}/thinking
```
