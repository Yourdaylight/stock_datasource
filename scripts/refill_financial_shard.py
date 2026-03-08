import argparse
from datetime import datetime

from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client


def log(msg: str):
    print(f"[{datetime.now()}] {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--start-date", default="20100101")
    parser.add_argument("--end-date", default="20260331")
    args = parser.parse_args()

    plugin_manager.discover_plugins()
    plugin = plugin_manager.get_plugin(args.plugin)
    if not plugin:
        log(f"missing plugin={args.plugin}")
        return

    stocks = db_client.execute_query(
        "SELECT DISTINCT ts_code FROM ods_stock_basic WHERE list_status='L' ORDER BY ts_code"
    )
    codes = stocks["ts_code"].tolist()
    shard_codes = [code for i, code in enumerate(codes) if i % args.total == args.shard]

    log(f"start plugin={args.plugin} shard={args.shard}/{args.total} stocks={len(shard_codes)}")

    ok = 0
    fail = 0
    for idx, ts_code in enumerate(shard_codes, start=1):
        kwargs = {"ts_code": ts_code}
        if args.plugin in {
            "tushare_income",
            "tushare_balancesheet",
            "tushare_cashflow",
            "tushare_finace_indicator",
            "tushare_fina_audit",
        }:
            kwargs["start_date"] = args.start_date
            kwargs["end_date"] = args.end_date
        elif args.plugin in {"tushare_forecast", "tushare_express"}:
            kwargs["start_date"] = args.start_date
            kwargs["end_date"] = args.end_date

        result = plugin.run(**kwargs)
        if result.get("status") == "success":
            ok += 1
        else:
            fail += 1
            log(f"fail plugin={args.plugin} ts_code={ts_code} err={result.get('error')}")

        if idx % 50 == 0:
            log(f"progress plugin={args.plugin} shard={args.shard} done={idx}/{len(shard_codes)} ok={ok} fail={fail}")

    log(f"done plugin={args.plugin} shard={args.shard} ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
