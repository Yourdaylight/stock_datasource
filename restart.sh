#!/bin/bash
# 前后端重启脚本

set -e

echo "=========================================="
echo "  Stock Datasource 重启脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 停止现有进程
echo -e "${YELLOW}[1/4]${NC} 停止现有进程..."

# 查找并停止占用8000端口的进程
BACKEND_PIDS=$(lsof -t -i :8000 2>/dev/null || true)
if [ -n "$BACKEND_PIDS" ]; then
    echo -e "  ${YELLOW}停止后端进程 (PID: $BACKEND_PIDS)${NC}"
    kill -9 $BACKEND_PIDS 2>/dev/null || true
    sleep 2
else
    echo -e "  ${GREEN}端口8000未占用${NC}"
fi

# 查找并停止前端进程（可能在3000-3010之间）
for port in 3000 3001 3002 3003 3004 3005 5173; do
    FRONTEND_PIDS=$(lsof -t -i :$port 2>/dev/null || true)
    if [ -n "$FRONTEND_PIDS" ]; then
        echo -e "  ${YELLOW}停止前端进程 (Port: $port, PID: $FRONTEND_PIDS)${NC}"
        kill -9 $FRONTEND_PIDS 2>/dev/null || true
    fi
done

# 额外清理可能残留的进程
pkill -f "stock_datasource.services.http_server" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo -e "  ${GREEN}✓ 所有进程已停止${NC}"
echo ""

# 2. 确认端口已释放
echo -e "${YELLOW}[2/4]${NC} 检查端口状态..."
PORT_8000=$(lsof -t -i :8000 2>/dev/null || true)
PORT_FRONT=$(lsof -t -i :3000 -i :3001 -i :3002 -i :3003 -i :3004 -i :3005 -i :5173 2>/dev/null || true)

if [ -n "$PORT_8000" ]; then
    echo -e "  ${RED}✗ 端口8000仍被占用 (PID: $PORT_8000)${NC}"
    exit 1
else
    echo -e "  ${GREEN}✓ 端口8000已释放${NC}"
fi

if [ -n "$PORT_FRONT" ]; then
    echo -e "  ${RED}✗ 前端端口仍被占用 (PID: $PORT_FRONT)${NC}"
    exit 1
else
    echo -e "  ${GREEN}✓ 前端端口已释放${NC}"
fi
echo ""

# 3. 启动后端
echo -e "${YELLOW}[3/4]${NC} 启动后端服务..."
cd "$SCRIPT_DIR"
mkdir -p "$SCRIPT_DIR/logs"

# 后台启动后端
nohup uv run python -m stock_datasource.services.http_server > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  后端PID: $BACKEND_PID"

# 等待后端启动并验证（考虑初始化耗时较长，初始化约2分钟）
MAX_BACKEND_WAIT=150
for i in $(seq 1 $MAX_BACKEND_WAIT); do
    sleep 1
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ 后端已启动 (http://0.0.0.0:8000)${NC}"
        break
    fi
    if [ $i -eq $MAX_BACKEND_WAIT ]; then
        echo -e "  ${RED}✗ 后端启动超时（已等待 ${MAX_BACKEND_WAIT}s）${NC}"
        echo "  查看日志: tail -f $SCRIPT_DIR/logs/backend.log"
        exit 1
    fi
done
echo ""

# 4. 启动前端
echo -e "${YELLOW}[4/4]${NC} 启动前端服务..."
cd "$SCRIPT_DIR/frontend"

# 后台启动前端
nohup npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  前端PID: $FRONTEND_PID"

# 等待前端启动并获取实际端口
FRONTEND_PORT=""
for i in {1..25}; do
    sleep 1
    # 检查可能的端口
    for port in 3000 3001 3002 3003 3004 3005 5173; do
        if lsof -t -i :$port > /dev/null 2>&1; then
            FRONTEND_PORT=$port
            break 2
        fi
    done
    if [ -n "$FRONTEND_PORT" ]; then
        break
    fi
    if [ $i -eq 25 ]; then
        echo -e "  ${YELLOW}⚠ 前端启动较慢，请稍后检查${NC}"
    fi
done

if [ -n "$FRONTEND_PORT" ]; then
    echo -e "  ${GREEN}✓ 前端已启动 (http://0.0.0.0:$FRONTEND_PORT)${NC}"
fi
echo ""

# 完成
echo "=========================================="
echo -e "${GREEN}  ✓ 所有服务已成功重启！${NC}"
echo "=========================================="
echo ""
echo -e "${BLUE}后端 API:${NC} http://0.0.0.0:8000"
echo -e "${BLUE}前端界面:${NC} http://0.0.0.0:$FRONTEND_PORT"
echo ""
echo -e "${BLUE}查看日志:${NC}"
echo "  后端: tail -f $SCRIPT_DIR/logs/backend.log"
echo "  前端: tail -f $SCRIPT_DIR/logs/frontend.log"
echo ""
echo -e "${BLUE}停止服务:${NC}"
echo "  停止后端: kill -9 $BACKEND_PID"
echo "  停止前端: kill -9 $FRONTEND_PID"
echo ""
