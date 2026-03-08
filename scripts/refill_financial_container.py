from datetime import datetime
from stock_datasource.core.plugin_manager import plugin_manager


def log(msg: str) -> None:
    print(f"[{datetime.now()}] {msg}", flush=True)


def run_plugin(name: str, **kwargs):
    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        log(f"MISSING plugin={name}")
        return False, {"error": "missing plugin"}
    log(f"RUN plugin={name} kwargs={kwargs}")
    result = plugin.run(**kwargs)
    status = result.get("status")
    load = result.get("steps", {}).get("load", {})
    log(f"DONE plugin={name} status={status} load={load}")
    return status == "success", result


def main():
    log("financial refill start")
    plugin_manager.discover_plugins()

    main_plugins = [
        ("tushare_income", {"start_date": "20100101", "end_date": "20260331"}),
        ("tushare_balancesheet", {"start_date": "20100101", "end_date": "20260331"}),
        ("tushare_cashflow", {"start_date": "20100101", "end_date": "20260331"}),
        ("tushare_forecast", {}),
        ("tushare_express", {}),
        ("tushare_finace_indicator", {"start_date": "20100101", "end_date": "20260331", "batch_size": 20}),
        ("tushare_fina_audit", {"start_date": "20100101", "end_date": "20260331"}),
    ]

    ok = 0
    fail = 0
    for name, kwargs in main_plugins:
        success, _ = run_plugin(name, **kwargs)
        if success:
            ok += 1
        else:
            fail += 1

    vip_plugins = ["tushare_income_vip", "tushare_balancesheet_vip", "tushare_cashflow_vip"]
    periods = []
    for year in range(2010, 2026):
        periods.extend([f"{year}0331", f"{year}0630", f"{year}0930", f"{year}1231"])

    for name in vip_plugins:
        plugin = plugin_manager.get_plugin(name)
        if not plugin:
            log(f"MISSING plugin={name}")
            fail += 1
            continue
        p_ok = 0
        p_fail = 0
        log(f"RUN VIP plugin={name} periods={len(periods)}")
        for period in periods:
            result = plugin.run(period=period, report_type="1")
            if result.get("status") == "success":
                p_ok += 1
            else:
                p_fail += 1
                log(f"FAIL VIP plugin={name} period={period} err={result.get('error')}")
        log(f"DONE VIP plugin={name} ok={p_ok} fail={p_fail}")
        if p_fail == 0:
            ok += 1
        else:
            fail += 1

    log(f"financial refill done ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
