import importlib.util
import sys
from pathlib import Path


def load_receive_push_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "collection_and_push" / "receive_push_data.py"
    spec = importlib.util.spec_from_file_location("receive_push_data_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_effective_scope_uses_stricter_policy():
    module = load_receive_push_module()
    claims = {
        "sub": "alice",
        "rev": 2,
        "scope": {
            "markets": ["CN", "HK"],
            "levels": ["L1"],
            "symbols": {"mode": "all", "list": []},
            "quota": {"max_subs": 5},
        },
    }
    policy = {
        "user_id": "alice",
        "markets": ["CN"],
        "levels": ["L1"],
        "symbols": {"mode": "list", "list": ["000001.SZ", "600519.SH"]},
        "max_subs": 2,
        "revision": 5,
    }

    effective = module.build_effective_subscription_scope(claims, policy)

    assert effective["user_id"] == "alice"
    assert effective["markets"] == {"CN"}
    assert effective["max_subs"] == 2
    assert effective["symbol_mode"] == "list"
    assert effective["symbol_list"] == {"000001.SZ", "600519.SH"}
    assert effective["revision"] == 5


def test_validate_subscription_symbols_enforces_quota_and_market():
    module = load_receive_push_module()
    effective = {
        "markets": {"CN"},
        "levels": {"L1"},
        "max_subs": 2,
        "symbol_mode": "all",
        "symbol_list": set(),
    }

    accepted, rejected = module.validate_subscription_symbols(
        ["000001.SZ", "600519.SH", "00700.HK", "000001.SZ"],
        effective,
    )

    assert accepted == ["000001.SZ", "600519.SH"]
    assert rejected == [{"symbol": "00700.HK", "reason": "market_not_allowed"}]


def test_subscription_snapshot_reads_from_sqlite_snapshot(tmp_path: Path):
    module = load_receive_push_module()
    cfg = module.ReceiverConfig(
        data_dir=str(tmp_path),
        flush_interval_seconds=1,
        flush_max_items=100,
        subscription_step_seconds=3,
    )
    store = module.PushDataStore(cfg)

    ack = store.store_batch(
        {
            "schema_version": "v2",
            "mode": "raw_tick_batch",
            "batch_seq": 1,
            "event_time": "2026-03-17T10:00:00Z",
            "market": "a_stock",
            "source_api": "tushare_rt_k",
            "count": 2,
            "first_stream_id": "1-0",
            "last_stream_id": "1-1",
            "items": [
                {"stream_id": "1-0", "ts_code": "000001.SZ", "version": "1", "shard_id": 0, "tick": {"ts_code": "000001.SZ", "close": 10.5}},
                {"stream_id": "1-1", "ts_code": "600519.SH", "version": "1", "shard_id": 1, "tick": {"ts_code": "600519.SH", "close": 1690.0}},
            ],
        }
    )
    assert ack["accepted_count"] == 2

    hk_ack = store.store_batch(
        {
            "schema_version": "v2",
            "mode": "raw_tick_batch",
            "batch_seq": 2,
            "event_time": "2026-03-17T10:00:03Z",
            "market": "hk",
            "source_api": "finnhub_rt_k",
            "count": 1,
            "first_stream_id": "2-0",
            "last_stream_id": "2-0",
            "items": [
                {"stream_id": "2-0", "ts_code": "00700.HK", "version": "1", "shard_id": 0, "tick": {"ts_code": "00700.HK", "close": 380.0}},
            ],
        }
    )
    assert hk_ack["accepted_count"] == 1

    flush_result = store.process_spool_once(max_items=100)
    assert flush_result["processed"] == 3
    assert flush_result["upserts"] == 3

    snapshot = store.get_subscription_snapshot(["000001.SZ", "00700.HK", "600519.SH"], 5)

    assert snapshot["count"] == 3
    assert snapshot["step_seconds"] == 5
    assert snapshot["missing"] == []
    assert {item["ts_code"] for item in snapshot["data"]} == {"000001.SZ", "00700.HK", "600519.SH"}


def test_apply_policies_persists_to_sqlite(tmp_path: Path):
    module = load_receive_push_module()
    cfg = module.ReceiverConfig(data_dir=str(tmp_path))
    store = module.PushDataStore(cfg)

    applied = store.apply_policies(
        {
            "users": [
                {
                    "user_id": "alice",
                    "markets": ["CN"],
                    "levels": ["L1"],
                    "symbols": {"mode": "list", "list": ["000001.SZ"]},
                    "max_subs": 1,
                    "revision": 7,
                }
            ]
        }
    )

    assert applied == 1
    policy = store.get_policy("alice")
    assert policy is not None
    assert policy["revision"] == 7
    assert policy["symbols"]["list"] == ["000001.SZ"]


def test_sync_user_subscriptions_persists_manifest(tmp_path: Path):
    module = load_receive_push_module()
    cfg = module.ReceiverConfig(data_dir=str(tmp_path))
    store = module.PushDataStore(cfg)
    effective = {
        "user_id": "alice",
        "markets": {"CN"},
        "levels": {"L1"},
        "max_subs": 2,
        "symbol_mode": "all",
        "symbol_list": set(),
        "revision": 9,
    }

    result = store.sync_user_subscriptions(
        "alice",
        ["000001.SZ", "600519.SH", "00700.HK"],
        effective,
        mode="replace",
    )

    assert result["accepted_symbols"] == ["000001.SZ", "600519.SH"]
    assert result["rejected_symbols"] == [{"symbol": "00700.HK", "reason": "market_not_allowed"}]
    assert store.get_user_subscriptions("alice") == ["000001.SZ", "600519.SH"]


def test_subscription_endpoints_use_registered_symbols(tmp_path: Path):
    module = load_receive_push_module()

    def fake_verify(_token: str, _path: str):
        return True, {
            "sub": "alice",
            "rev": 3,
            "scope": {
                "markets": ["CN"],
                "levels": ["L1"],
                "symbols": {"mode": "all", "list": []},
                "quota": {"max_subs": 2},
            },
        }, ""

    module.verify_subscription_token = fake_verify
    cfg = module.ReceiverConfig(data_dir=str(tmp_path), jwt_public_key_path="/tmp/dummy.pem", flush_interval_seconds=30)
    app = module.create_app(cfg)
    client = app.test_client()
    store = app.config["push_data_store"]

    try:
        policy_resp = client.post(
            "/api/v1/rt-kline/policies/apply",
            json={
                "users": [
                    {
                        "user_id": "alice",
                        "markets": ["CN"],
                        "levels": ["L1"],
                        "symbols": {"mode": "all", "list": []},
                        "max_subs": 2,
                        "revision": 5,
                    }
                ]
            },
        )
        assert policy_resp.status_code == 200

        sync_resp = client.post(
            "/api/v1/rt-kline/subscription/sync",
            headers={"Authorization": "Bearer demo-token"},
            json={"mode": "replace", "symbols": ["000001.SZ", "600519.SH"]},
        )
        assert sync_resp.status_code == 200
        assert sync_resp.get_json()["accepted_symbols"] == ["000001.SZ", "600519.SH"]

        client.post(
            "/api/v1/rt-kline/push",
            json={
                "schema_version": "v2",
                "mode": "raw_tick_batch",
                "batch_seq": 1,
                "event_time": "2026-03-17T10:00:00Z",
                "market": "a_stock",
                "source_api": "tushare_rt_k",
                "count": 2,
                "first_stream_id": "1-0",
                "last_stream_id": "1-1",
                "items": [
                    {"stream_id": "1-0", "ts_code": "000001.SZ", "version": "1", "shard_id": 0, "tick": {"ts_code": "000001.SZ", "close": 10.5}},
                    {"stream_id": "1-1", "ts_code": "600519.SH", "version": "1", "shard_id": 1, "tick": {"ts_code": "600519.SH", "close": 1690.0}},
                ],
            },
        )
        store.process_spool_once(max_items=100)

        list_resp = client.get(
            "/api/v1/rt-kline/subscription/list",
            headers={"Authorization": "Bearer demo-token"},
        )
        assert list_resp.status_code == 200
        assert list_resp.get_json()["subscribed_symbols"] == ["000001.SZ", "600519.SH"]

        latest_resp = client.get(
            "/api/v1/rt-kline/subscription/latest",
            headers={"Authorization": "Bearer demo-token"},
        )
        assert latest_resp.status_code == 200
        latest_json = latest_resp.get_json()
        assert latest_json["accepted_symbols"] == ["000001.SZ", "600519.SH"]
        assert latest_json["count"] == 2

        subset_resp = client.get(
            "/api/v1/rt-kline/subscription/latest?symbols=000001.SZ,00700.HK",
            headers={"Authorization": "Bearer demo-token"},
        )
        assert subset_resp.status_code == 200
        subset_json = subset_resp.get_json()
        assert subset_json["accepted_symbols"] == ["000001.SZ"]
        assert subset_json["rejected_symbols"] == [{"symbol": "00700.HK", "reason": "not_subscribed"}]
    finally:
        store.stop_builder()