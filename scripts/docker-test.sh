#!/bin/bash
# scripts/docker-test.sh - Test Docker container services
#
# Usage:
#   ./scripts/docker-test.sh           # Run all tests
#   ./scripts/docker-test.sh backend   # Test backend only
#   ./scripts/docker-test.sh redis     # Test Redis only
#   ./scripts/docker-test.sh clickhouse # Test ClickHouse only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default ports (can be overridden by environment)
BACKEND_PORT="${BACKEND_PORT:-6666}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
REDIS_PORT="${REDIS_PORT:-6379}"
CLICKHOUSE_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8123}"
LANGFUSE_PORT="${LANGFUSE_PORT:-3000}"
REDIS_PASSWORD="${REDIS_PASSWORD:-stockredis123}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

passed=0
failed=0

# Determine if we need sudo for docker
DOCKER_CMD="docker"
if ! docker ps &> /dev/null 2>&1; then
    if sudo docker ps &> /dev/null 2>&1; then
        DOCKER_CMD="sudo docker"
    fi
fi

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((passed++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((failed++))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

# Test Backend Service
test_backend() {
    echo ""
    echo "========================================"
    echo "Testing Backend Service (port $BACKEND_PORT)"
    echo "========================================"
    
    # Health check
    log_test "Backend health check..."
    if response=$(curl -sf "http://localhost:$BACKEND_PORT/health" 2>/dev/null); then
        log_pass "Backend health check"
        echo "  Response: $response"
    else
        log_fail "Backend health check - service not responding"
        return 1
    fi
    
    # Root endpoint
    log_test "Backend root endpoint..."
    if response=$(curl -sf "http://localhost:$BACKEND_PORT/" 2>/dev/null); then
        log_pass "Backend root endpoint"
        echo "  Response: $response"
    else
        log_fail "Backend root endpoint"
    fi
    
    # Cache stats
    log_test "Cache stats endpoint..."
    if response=$(curl -sf "http://localhost:$BACKEND_PORT/api/cache/stats" 2>/dev/null); then
        log_pass "Cache stats endpoint"
        echo "  Response: $response"
    else
        log_fail "Cache stats endpoint"
    fi
    
    # Test cache set/get
    log_test "Cache set/get operations..."
    test_key="test:docker:$(date +%s)"
    test_value='{"test": true, "timestamp": "'$(date -Iseconds)'"}'
    
    # Set
    set_response=$(curl -sf -X POST "http://localhost:$BACKEND_PORT/api/cache/set" \
        -H "Content-Type: application/json" \
        -d "{\"key\": \"$test_key\", \"value\": $test_value, \"ttl\": 60}" 2>/dev/null)
    
    if echo "$set_response" | grep -q '"success":true'; then
        log_pass "Cache set operation"
        
        # Get
        get_response=$(curl -sf "http://localhost:$BACKEND_PORT/api/cache/get/$test_key" 2>/dev/null)
        if echo "$get_response" | grep -q '"found":true'; then
            log_pass "Cache get operation"
            
            # Delete
            del_response=$(curl -sf -X DELETE "http://localhost:$BACKEND_PORT/api/cache/delete/$test_key" 2>/dev/null)
            if echo "$del_response" | grep -q '"success":true'; then
                log_pass "Cache delete operation"
            else
                log_fail "Cache delete operation"
            fi
        else
            log_fail "Cache get operation"
        fi
    else
        log_fail "Cache set operation - Redis may not be connected"
    fi
}

# Test Frontend Service
test_frontend() {
    echo ""
    echo "========================================"
    echo "Testing Frontend Service (port $FRONTEND_PORT)"
    echo "========================================"
    
    log_test "Frontend health check..."
    if curl -sf "http://localhost:$FRONTEND_PORT/health" > /dev/null 2>&1; then
        log_pass "Frontend health check"
    else
        # Try root page
        if curl -sf "http://localhost:$FRONTEND_PORT/" > /dev/null 2>&1; then
            log_pass "Frontend root page accessible"
        else
            log_fail "Frontend not responding"
        fi
    fi
}

# Test Redis Service
test_redis() {
    echo ""
    echo "========================================"
    echo "Testing Redis Service (port $REDIS_PORT)"
    echo "========================================"
    
    # Try multiple container names (stock-redis or langfuse-redis-1)
    REDIS_CONTAINER=""
    for name in stock-redis langfuse-redis-1; do
        if $DOCKER_CMD ps --format "{{.Names}}" 2>/dev/null | grep -q "^${name}$"; then
            REDIS_CONTAINER=$name
            break
        fi
    done
    
    if [ -z "$REDIS_CONTAINER" ]; then
        log_skip "No Redis container found (stock-redis or langfuse-redis-1)"
        return 0
    fi
    
    log_test "Redis PING via docker ($REDIS_CONTAINER)..."
    if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG; then
        log_pass "Redis PING via docker"
    else
        # Try without password (langfuse redis may not have password)
        if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli ping 2>/dev/null | grep -q PONG; then
            log_pass "Redis PING via docker (no auth)"
        else
            log_fail "Redis PING via docker"
            return 1
        fi
    fi
    
    log_test "Redis INFO via docker..."
    if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli -a "$REDIS_PASSWORD" info server 2>/dev/null | head -5; then
        log_pass "Redis INFO"
    else
        if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli info server 2>/dev/null | head -5; then
            log_pass "Redis INFO (no auth)"
        else
            log_fail "Redis INFO"
        fi
    fi
    
    # Test set/get
    log_test "Redis SET/GET via docker..."
    test_key="docker:test:$(date +%s)"
    if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli -a "$REDIS_PASSWORD" SET "$test_key" "test_value" EX 60 2>/dev/null | grep -q OK; then
        if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli -a "$REDIS_PASSWORD" GET "$test_key" 2>/dev/null | grep -q "test_value"; then
            log_pass "Redis SET/GET"
            $DOCKER_CMD exec $REDIS_CONTAINER redis-cli -a "$REDIS_PASSWORD" DEL "$test_key" > /dev/null 2>&1
        else
            log_fail "Redis GET"
        fi
    else
        # Try without password
        if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli SET "$test_key" "test_value" EX 60 2>/dev/null | grep -q OK; then
            if $DOCKER_CMD exec $REDIS_CONTAINER redis-cli GET "$test_key" 2>/dev/null | grep -q "test_value"; then
                log_pass "Redis SET/GET (no auth)"
                $DOCKER_CMD exec $REDIS_CONTAINER redis-cli DEL "$test_key" > /dev/null 2>&1
            else
                log_fail "Redis GET"
            fi
        else
            log_fail "Redis SET"
        fi
    fi
}

# Test ClickHouse Service
test_clickhouse() {
    echo ""
    echo "========================================"
    echo "Testing ClickHouse Service (port $CLICKHOUSE_HTTP_PORT)"
    echo "========================================"
    
    log_test "ClickHouse PING..."
    if curl -sf "http://localhost:$CLICKHOUSE_HTTP_PORT/ping" > /dev/null 2>&1; then
        log_pass "ClickHouse PING"
    else
        log_fail "ClickHouse PING"
        return 1
    fi
    
    log_test "ClickHouse SELECT 1..."
    if response=$(curl -sf "http://localhost:$CLICKHOUSE_HTTP_PORT/?query=SELECT%201" 2>/dev/null); then
        log_pass "ClickHouse SELECT 1"
        echo "  Response: $response"
    else
        log_fail "ClickHouse SELECT 1"
    fi
    
    log_test "ClickHouse databases..."
    if response=$(curl -sf "http://localhost:$CLICKHOUSE_HTTP_PORT/?query=SHOW%20DATABASES" 2>/dev/null); then
        log_pass "ClickHouse SHOW DATABASES"
        echo "  Databases: $(echo "$response" | tr '\n' ', ')"
    else
        log_fail "ClickHouse SHOW DATABASES"
    fi
    
    # Check stock_data database
    log_test "ClickHouse stock_data database..."
    if curl -sf "http://localhost:$CLICKHOUSE_HTTP_PORT/?query=SHOW%20DATABASES" 2>/dev/null | grep -q "stock_data"; then
        log_pass "stock_data database exists"
    else
        log_skip "stock_data database not created yet"
    fi
}

# Test Langfuse Service (optional)
test_langfuse() {
    echo ""
    echo "========================================"
    echo "Testing Langfuse Service (port $LANGFUSE_PORT)"
    echo "========================================"
    
    log_test "Langfuse web UI..."
    if curl -sf "http://localhost:$LANGFUSE_PORT/" > /dev/null 2>&1; then
        log_pass "Langfuse web UI accessible"
    else
        log_skip "Langfuse not running (optional)"
    fi
}

# Test Docker containers status
test_containers() {
    echo ""
    echo "========================================"
    echo "Docker Container Status"
    echo "========================================"
    
    echo ""
    $DOCKER_CMD ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "stock-|langfuse" || echo "No stock-* or langfuse containers running"
    echo ""
}

# Print summary
print_summary() {
    echo ""
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo -e "Passed: ${GREEN}$passed${NC}"
    echo -e "Failed: ${RED}$failed${NC}"
    echo ""
    
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# Main
case "${1:-all}" in
    backend)
        test_backend
        ;;
    frontend)
        test_frontend
        ;;
    redis)
        test_redis
        ;;
    clickhouse|ch)
        test_clickhouse
        ;;
    langfuse)
        test_langfuse
        ;;
    containers|status)
        test_containers
        ;;
    all)
        test_containers
        test_backend
        test_frontend
        test_redis
        test_clickhouse
        test_langfuse
        ;;
    *)
        echo "Usage: $0 [backend|frontend|redis|clickhouse|langfuse|containers|all]"
        exit 1
        ;;
esac

print_summary
