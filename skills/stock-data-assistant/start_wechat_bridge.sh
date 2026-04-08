#!/usr/bin/env bash
# ============================================================
# start_wechat_bridge.sh — 一键启动微信联动服务
#
# 功能:
#   1. 检查并自动下载 picoclaw
#   2. 从 .env 生成 picoclaw 配置
#   3. 启动 picoclaw 并开启微信 channel
#   4. （可选）启动实时数据 WebSocket 订阅
#
# 用法:
#   bash skills/stock-data-assistant/start_wechat_bridge.sh [选项]
#
#   选项:
#     --no-rt         不启动实时数据订阅
#     --symbols SYM   指定默认订阅股票代码 (逗号分隔)
#     --port PORT     picoclaw gateway 端口 (默认 18790)
#     --config PATH   指定已有的 picoclaw 配置文件
#     --stop          停止所有相关进程
#     --status        查看运行状态
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_DIR="$PROJECT_ROOT/.local"
BIN_DIR="$LOCAL_DIR/bin"
PID_FILE="$LOCAL_DIR/picoclaw.pid"
RT_PID_FILE="$LOCAL_DIR/subscribe_rt.pid"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${CYAN}━━━ $* ━━${NC}\n"; }

# 默认参数
NO_RT=false
SYMBOLS=""
GATEWAY_PORT=18790
CONFIG_PATH=""
ACTION="start"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-rt)      NO_RT=true; shift ;;
        --symbols)    SYMBOLS="$2"; shift 2;;
        --port)       GATEWAY_PORT="$2"; shift 2 ;;
        --config)     CONFIG_PATH="$2"; shift 2 ;;
        --stop)       ACTION="stop"; shift ;;
        --status)     ACTION="status"; shift ;;
        *)            log_error "未知参数: $1"; exit 1 ;;
    esac
done

# ---- stop 动作 ----
if [[ "$ACTION" == "stop" ]]; then
    log_step "停止微信联动服务..."
    stopped=0
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && log_info "已停止 picoclaw (PID: $PID)" || true
            stopped=$((stopped+1))
        fi
        rm -f "$PID_FILE"
    fi
    if [[ -f "$RT_PID_FILE" ]]; then
        PID=$(cat "$RT_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && log_info "已停止实时数据订阅 (PID: $PID)" || true
            stopped=$((stopped+1))
        fi
        rm -f "$RT_PID_FILE"
    fi
    if [[ $stopped -eq 0 ]]; then
        log_info "没有找到运行中的服务"
    else
        log_info "共停止 $stopped 个服务"
    fi
    exit 0
fi

# ---- status 动作 ----
if [[ "$ACTION" == "status" ]]; then
    echo "=== 微信联动服务状态 ==="
    echo ""

    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "  picoclaw:     ${GREEN}运行中${NC} (PID: $PID, Port: $GATEWAY_PORT)"
        else
            echo -e "  picoclaw:     ${RED}已停止${NC} (stale PID file)"
        fi
    else
        echo -e "  picoclaw:     ${YELLOW}未启动${NC}"
    fi

    if [[ -f "$RT_PID_FILE" ]]; then
        PID=$(cat "$RT_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "  RT 订阅:      ${GREEN}运行中${NC} (PID: $PID, WS: 8765)"
        else
            echo -e "  RT 订阅:      ${RED}已停止${NC} (stale PID file)"
        fi
    else
        echo -e "  RT 订阅:      ${YELLOW}未启动${NC}"
    fi

    echo ""
    echo "配置文件: $LOCAL_DIR/picoclaw.yaml"
    [[ -f "$LOCAL_DIR/picoclaw.yaml" ]] && echo -e "  状态: ${GREEN}存在${NC}" || echo -e "  状态: ${RED}不存在${NC}"
    echo ""
    exit 0
fi

# ======================== start 动作 ========================

log_step "Step 1/4: 检查 picoclaw"
PICOCLAW_BIN="$BIN_DIR/picoclaw"
if [[ ! -x "$PICOCLAW_BIN" ]]; then
    log_info "picoclaw 未安装，正在自动下载..."
    bash "$SCRIPT_DIR/setup_picoclaw.sh"
    if [[ ! -x "$PICOCLAW_BIN" ]]; then
        log_error "picoclaw 安装失败"
        exit 1
    fi
else
    EXISTING_VER=$("$PICOCLAW_BIN" --version 2>/dev/null || echo "unknown")
    log_info "picoclaw 已存在 ($EXISTING_VER)"
fi

log_step "Step 2/4: 生成配置文件"
if [[ -n "$CONFIG_PATH" ]] && [[ -f "$CONFIG_PATH" ]]; then
    CONFIG_FILE="$CONFIG_PATH"
    log_info "使用已有配置: $CONFIG_FILE"
else
    CONFIG_FILE="$LOCAL_DIR/picoclaw.yaml"
    CMD=(python3 "$SCRIPT_DIR/generate_picoclaw_config.py" "--output" "$CONFIG_FILE")
    [[ -n "${STOCK_MCP_TOKEN:-}" ]] && CMD+=(--mcp-token "$STOCK_MCP_TOKEN")
    "${CMD[@]}"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "配置文件生成失败"
        exit 1
    fi
fi

log_step "Step 3/4: 启动 picoclaw (Gateway + 微信 Channel)"
export PATH="$BIN_DIR:$PATH"

# 检查是否已在运行
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log_warn "picoclaw 已经在运行 (PID: $OLD_PID)，先停止旧进程..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

log_info "启动 picoclaw Gateway (端口: $GATEWAY_PORT)..."
nohup picoclaw run --config "$CONFIG_FILE" >"$LOCAL_DIR/picoclaw.log" 2>&1 &
PICOCLAW_PID=$!
echo "$PICOCLAW_PID" > "$PID_FILE"

# 等待启动
sleep 2
if kill -0 "$PICOCLAW_PID" 2>/dev/null; then
    log_info "✅ picoclaw 已启动 (PID: $PICOCLAW_PID, 日志: $LOCAL_DIR/picoclaw.log)"
else
    log_error "picoclaw 启动失败，查看日志: tail -20 $LOCAL_DIR/picoclaw.log"
    cat "$LOCAL_DIR/picoclaw.log" 2>/dev/null || true
    exit 1
fi

log_step "Step 4/4: 启动实时数据订阅"
if [[ "$NO_RT" == "true" ]]; then
    log_info "跳过实时数据订阅 (--no-rt)"
else
    DEFAULT_SYMBOLS="${SYMBOLS:-00700.HK,09988.HK,600519.SH}"
    log_info "启动 WebSocket 实时数据订阅 (股票: $DEFAULT_SYMBOLS)..."

    SUBSCRIBE_SCRIPT="$PROJECT_ROOT/skills/stock-rt-subscribe/scripts/subscribe_client.py"
    if [[ -f "$SUBSCRIBE_SCRIPT" ]]; then
        # 将逗号分隔的符号转为空格分隔
        RT_SYMBOLS=$(echo "$DEFAULT_SYMBOLS" | tr ',' ' ')
        nohup python3 "$SUBSCRIBE_SCRIPT" \
            --symbols $RT_SYMBOLS \
            --ws-port 8765 \
            >"$LOCAL_DIR/subscribe_rt.log" 2>&1 &
        RT_PID=$!
        echo "$RT_PID" > "$RT_PID_FILE"
        sleep 1
        if kill -0 "$RT_PID" 2>/dev/null; then
            log_info "✅ 实时数据订阅已启动 (PID: $RT_PID, WS: ws://localhost:8765)"
        else
            log_warn "实时数据订阅启动失败（不影响主功能），日志: $LOCAL_DIR/subscribe_rt.log"
        fi
    else
        log_warn "未找到订阅脚本: $SUBSCRIBE_SCRIPT，跳过实时数据订阅"
    fi
fi

# ======================== 完成 ========================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 微信联动服务已就绪！${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  📱 微信登录:"
echo "     执行以下命令显示微信登录二维码:"
echo "     picoclaw auth weixin"
echo ""
echo "  🔧 服务状态:"
echo "     查看状态:  bash $0 --status"
echo "     停止服务:  bash $0 --stop"
echo "     重启服务:  bash $0"
echo ""
echo "  📋 日志位置:"
echo "     picoclaw 日志:  $LOCAL_DIR/picoclaw.log"
echo "     RT 订阅日志:    $LOCAL_DIR/subscribe_rt.log"
echo "     配置文件:       $CONFIG_FILE"
echo ""
echo "  💡 使用说明:"
echo "     扫码登录微信后，直接在微信中发送消息即可查询股票数据"
echo "     示例消息:"
echo "       「查一下贵州茅台最近30天的日K线」"
echo "       「腾讯控股现在多少钱」"
echo "       「帮我监控 00700.HK 涨跌幅超过2%告警」"
echo ""
