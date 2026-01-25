#!/usr/bin/env python3
"""Interface-level test for triggering predefined ETF full group.

This test runs entirely via HTTP endpoints:
- POST /api/auth/login (token generation)
- POST /api/datamanage/groups/predefined_etf_full/trigger
- GET  /api/datamanage/schedule/execution/{execution_id}
- GET  /api/datamanage/sync/status/{task_id}

Security notes:
- No hardcoded credentials.
- Creates a temporary admin user directly in DB (ClickHouse) with a random password,
  then logs in via the login API to obtain a JWT.
- Deactivates the temp user at the end.

Usage (inside backend container recommended):
  python scripts/test_predefined_etf_full_trigger_api.py --base-url http://localhost:6666 --start 2026-01-01 --end 2026-01-23
"""

from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _rand_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _date_range(start: date, end: date) -> List[str]:
    out: List[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _has_weekend(dates: List[str]) -> List[str]:
    weekend: List[str] = []
    for d in dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        if dt.weekday() >= 5:
            weekend.append(d)
    return weekend


@dataclass
class TempUser:
    user_id: str
    email: str
    password: str


def _create_temp_admin_user() -> TempUser:
    # Create user directly in ClickHouse so we don't depend on whitelist/config.
    from stock_datasource.modules.auth.service import AuthService

    auth = AuthService()
    auth._ensure_tables()

    user_id = str(uuid.uuid4())
    email = f"autotest_admin_{user_id[:8]}@example.com"
    password = _rand_password()
    password_hash = auth.hash_password(password)
    now = datetime.now()

    insert_query = """
        INSERT INTO users (id, email, username, password_hash, is_active, is_admin, created_at, updated_at)
        VALUES (%(id)s, %(email)s, %(username)s, %(password_hash)s, 1, 1, %(created_at)s, %(updated_at)s)
    """

    auth.client.execute(
        insert_query,
        {
            "id": user_id,
            "email": email,
            "username": "autotest_admin",
            "password_hash": password_hash,
            "created_at": now,
            "updated_at": now,
        },
    )

    return TempUser(user_id=user_id, email=email, password=password)


def _deactivate_user(user_id: str) -> None:
    from stock_datasource.models.database import db_client

    # ReplacingMergeTree: insert a newer row with is_active=0.
    now = datetime.now()
    db_client.execute(
        """
        INSERT INTO users (id, email, username, password_hash, is_active, is_admin, created_at, updated_at)
        SELECT id, email, username, password_hash, 0, is_admin, created_at, %(updated_at)s
        FROM users FINAL
        WHERE id = %(id)s
        LIMIT 1
        """,
        {"id": user_id, "updated_at": now},
    )


def _http_client():
    # Prefer httpx (usually present in FastAPI stacks), fallback to requests.
    try:
        import httpx  # type: ignore

        return "httpx", httpx
    except Exception:
        import requests  # type: ignore

        return "requests", requests


def _post_json(base_url: str, path: str, payload: dict, headers: Optional[dict] = None) -> Tuple[int, Any, str]:
    kind, lib = _http_client()
    url = base_url.rstrip("/") + path
    if kind == "httpx":
        r = lib.post(url, json=payload, headers=headers, timeout=30.0)
        text = r.text
        try:
            return r.status_code, r.json(), text
        except Exception:
            return r.status_code, None, text
    else:
        r = lib.post(url, json=payload, headers=headers, timeout=30.0)
        text = r.text
        try:
            return r.status_code, r.json(), text
        except Exception:
            return r.status_code, None, text


def _get_json(base_url: str, path: str, headers: Optional[dict] = None) -> Tuple[int, Any, str]:
    kind, lib = _http_client()
    url = base_url.rstrip("/") + path
    if kind == "httpx":
        r = lib.get(url, headers=headers, timeout=30.0)
        text = r.text
        try:
            return r.status_code, r.json(), text
        except Exception:
            return r.status_code, None, text
    else:
        r = lib.get(url, headers=headers, timeout=30.0)
        text = r.text
        try:
            return r.status_code, r.json(), text
        except Exception:
            return r.status_code, None, text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:6666")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-01-23")
    ap.add_argument("--group-id", default="predefined_etf_full")
    ap.add_argument("--poll-seconds", type=int, default=15)
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    trade_dates = _date_range(start, end)

    temp = _create_temp_admin_user()

    try:
        # 1) Login via API (token generation)
        code, obj, raw = _post_json(
            args.base_url,
            "/api/auth/login",
            {"email": temp.email, "password": temp.password},
            headers={"Content-Type": "application/json"},
        )
        if code != 200 or not isinstance(obj, dict) or not obj.get("access_token"):
            print("[FAIL] /api/auth/login failed", file=sys.stderr)
            print(f"status={code} body={raw}", file=sys.stderr)
            return 1

        token = obj["access_token"]
        authz = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 2) Verify admin via /api/auth/me
        code, me, raw = _get_json(args.base_url, "/api/auth/me", headers=authz)
        if code != 200 or not isinstance(me, dict) or not me.get("is_admin"):
            print("[FAIL] /api/auth/me not admin", file=sys.stderr)
            print(f"status={code} body={raw}", file=sys.stderr)
            return 1

        # 3) Trigger group
        code, trig, raw = _post_json(
            args.base_url,
            f"/api/datamanage/groups/{args.group_id}/trigger",
            {"task_type": "backfill", "trade_dates": trade_dates},
            headers=authz,
        )
        if code != 200 or not isinstance(trig, dict) or not trig.get("execution_id"):
            print("[FAIL] trigger group failed", file=sys.stderr)
            print(f"status={code} body={raw}", file=sys.stderr)
            return 1

        execution_id = trig["execution_id"]

        # 4) Fetch execution detail (poll a bit for tasks)
        deadline = time.time() + args.poll_seconds
        detail: Optional[dict] = None
        while time.time() < deadline:
            code, obj, raw = _get_json(
                args.base_url,
                f"/api/datamanage/schedule/execution/{execution_id}",
                headers=authz,
            )
            if code == 200 and isinstance(obj, dict) and obj.get("tasks"):
                detail = obj
                break
            time.sleep(1)

        if not detail:
            print("[FAIL] execution detail not available", file=sys.stderr)
            print(f"execution_id={execution_id}", file=sys.stderr)
            return 1

        tasks = detail.get("tasks") or []
        task_ids = [t.get("task_id") for t in tasks if isinstance(t, dict) and t.get("task_id")]
        if not task_ids:
            print("[FAIL] no task_ids in execution detail", file=sys.stderr)
            print(json.dumps(detail, ensure_ascii=False)[:1000], file=sys.stderr)
            return 1

        # 5) Validate each task's trade_dates
        failures: List[str] = []
        for tid in task_ids:
            code, st, raw = _get_json(args.base_url, f"/api/datamanage/sync/status/{tid}", headers=authz)
            if code != 200 or not isinstance(st, dict):
                failures.append(f"task {tid}: status fetch failed ({code})")
                continue

            plugin = st.get("plugin_name")
            dates = st.get("trade_dates") or []
            if plugin == "tushare_etf_basic":
                if len(dates) != 0:
                    failures.append(f"{plugin}: expected empty trade_dates, got {len(dates)}")
                continue

            if not isinstance(dates, list):
                failures.append(f"{plugin}: trade_dates not list")
                continue

            weekend = _has_weekend([str(x) for x in dates])
            if weekend:
                failures.append(f"{plugin}: weekend dates present: {weekend[:5]}")

            # A few known non-trading days within 2026-01-01..2026-01-04
            known_non_trading = {"2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"}
            bad = [d for d in dates if d in known_non_trading]
            if bad:
                failures.append(f"{plugin}: holiday/weekend not filtered: {bad}")

        if failures:
            print("[FAIL] Interface test failed", file=sys.stderr)
            print(f"execution_id={execution_id}", file=sys.stderr)
            for f in failures:
                print(f"- {f}", file=sys.stderr)
            return 1

        print("[PASS] Interface test passed")
        print(f"execution_id={execution_id}")
        print(f"group_id={args.group_id}")
        print(f"range={args.start}..{args.end} ({len(trade_dates)} calendar days)")
        print(f"tasks={len(task_ids)}")
        return 0

    finally:
        try:
            _deactivate_user(temp.user_id)
        except Exception:
            # Best-effort cleanup
            pass


if __name__ == "__main__":
    raise SystemExit(main())
