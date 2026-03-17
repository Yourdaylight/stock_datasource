#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:9100}"
PUSH_TOKEN="${PUSH_TOKEN:-${RT_KLINE_CLOUD_PUSH_TOKEN:-}}"
POLICY_TOKEN="${POLICY_TOKEN:-${RT_STOCK_POLICY_TOKEN:-}}"
STOCK_RT_TOKEN="${STOCK_RT_TOKEN:-}"
RUN_PUSH_TEST=1
RUN_POLICY_TEST=1
RUN_SUBSCRIPTION_TEST=1

usage() {
  cat <<'EOF'
Usage:
  BASE_URL=http://node:9100 ./scripts/collection_and_push/verify_receiver_flow.sh

Environment variables:
  BASE_URL         Receiver base URL, default http://127.0.0.1:9100
  PUSH_TOKEN       Push API bearer token
  POLICY_TOKEN     Policy API bearer token
  STOCK_RT_TOKEN   Realtime subscription JWT token for sync/list/latest checks

Options:
  --skip-push           Skip POST /api/v1/rt-kline/push verification
  --skip-policy         Skip POST /api/v1/rt-kline/policies/apply verification
  --skip-subscription   Skip subscription sync/list/latest verification
  -h, --help            Show this help

Examples:
  BASE_URL=http://127.0.0.1:9100 ./scripts/collection_and_push/verify_receiver_flow.sh
  BASE_URL=http://node:9100 PUSH_TOKEN=xxx ./scripts/collection_and_push/verify_receiver_flow.sh --skip-subscription
  BASE_URL=http://node:9100 POLICY_TOKEN=xxx STOCK_RT_TOKEN=jwt ./scripts/collection_and_push/verify_receiver_flow.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-push)
      RUN_PUSH_TEST=0
      ;;
    --skip-policy)
      RUN_POLICY_TEST=0
      ;;
    --skip-subscription)
      RUN_SUBSCRIPTION_TEST=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

print_section() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$1"
}

curl_json() {
  local method="$1"
  local url="$2"
  local token="$3"
  local body="${4:-}"
  local -a args
  args=(-sS -X "$method" "$url")
  if [[ -n "$token" ]]; then
    args+=(-H "Authorization: Bearer $token")
  fi
  if [[ -n "$body" ]]; then
    args+=(-H "Content-Type: application/json" -d "$body")
  fi
  curl "${args[@]}"
}

print_section "1/5 Health"
curl -sS "$BASE_URL/health"
printf '\n'

print_section "2/5 Stats"
curl -sS "$BASE_URL/stats"
printf '\n'

if [[ "$RUN_PUSH_TEST" -eq 1 ]]; then
  print_section "3/5 Push sample batch"
  if [[ -z "$PUSH_TOKEN" ]]; then
    echo "PUSH_TOKEN not set; running without Authorization header"
  fi
  SAMPLE_PUSH='{"schema_version":"v2","mode":"raw_tick_batch","batch_seq":900001,"event_time":"2026-03-17T10:00:00Z","market":"a_stock","source_api":"verify_receiver_flow","count":2,"first_stream_id":"900001-0","last_stream_id":"900001-1","items":[{"stream_id":"900001-0","ts_code":"000001.SZ","version":"1","shard_id":0,"tick":{"ts_code":"000001.SZ","market":"a_stock","close":10.52,"trade_date":"20260317"}},{"stream_id":"900001-1","ts_code":"600519.SH","version":"1","shard_id":1,"tick":{"ts_code":"600519.SH","market":"a_stock","close":1690.00,"trade_date":"20260317"}}]}'
  curl_json POST "$BASE_URL/api/v1/rt-kline/push" "$PUSH_TOKEN" "$SAMPLE_PUSH"
  printf '\n'

  print_section "4/5 Query latest snapshot"
  curl -sS "$BASE_URL/api/v1/rt-kline/latest?ts_code=000001.SZ"
  printf '\n'
fi

if [[ "$RUN_POLICY_TEST" -eq 1 ]]; then
  print_section "Policy apply"
  if [[ -z "$POLICY_TOKEN" ]]; then
    echo "POLICY_TOKEN not set; skip policy apply"
  else
    SAMPLE_POLICY='{"users":[{"user_id":"verify-user","markets":["CN"],"levels":["L1"],"symbols":{"mode":"list","list":["000001.SZ","600519.SH"]},"max_subs":2,"revision":1}]}'
    curl_json POST "$BASE_URL/api/v1/rt-kline/policies/apply" "$POLICY_TOKEN" "$SAMPLE_POLICY"
    printf '\n'
  fi
fi

if [[ "$RUN_SUBSCRIPTION_TEST" -eq 1 ]]; then
  print_section "5/5 Subscription sync/list/latest"
  if [[ -z "$STOCK_RT_TOKEN" ]]; then
    echo "STOCK_RT_TOKEN not set; skip subscription validation"
  else
    curl_json POST "$BASE_URL/api/v1/rt-kline/subscription/sync" "$STOCK_RT_TOKEN" '{"mode":"replace","symbols":["000001.SZ","600519.SH"]}'
    printf '\n'
    curl_json GET "$BASE_URL/api/v1/rt-kline/subscription/list" "$STOCK_RT_TOKEN"
    printf '\n'
    curl_json GET "$BASE_URL/api/v1/rt-kline/subscription/latest" "$STOCK_RT_TOKEN"
    printf '\n'
  fi
fi

print_section "Done"
echo "Verification requests completed against $BASE_URL"