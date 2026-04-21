"""Stock attribute matrix builder.

Joins 6 ClickHouse tables into a single per-stock attribute dict, cached 24h in Redis.
Used by the Akinator LLM service to make yes/no splitting decisions.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from stock_datasource.models.database import db_client
from stock_datasource.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)

CACHE_KEY = "akinator:stock_matrix:v1"
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours

# Index codes we care about (TuShare convention)
HS300_INDEX = "000300.SH"
SZ50_INDEX = "000016.SH"
ZZ500_INDEX = "000905.SH"


def _query(sql: str, params: dict | None = None) -> list[tuple]:
    """Run SQL via db_client, returning rows."""
    try:
        return db_client.execute(sql, params or {})
    except Exception as e:
        logger.error(f"Akinator SQL failed: {e}\nSQL: {sql[:200]}")
        return []


def _fetch_index_members() -> dict[str, set[str]]:
    """Return {hs300: set(ts_codes), sz50: set, zz500: set}."""
    result: dict[str, set[str]] = {"hs300": set(), "sz50": set(), "zz500": set()}

    sql = """
        SELECT index_code, con_code
        FROM ods_index_member FINAL
        WHERE index_code IN (%(hs300)s, %(sz50)s, %(zz500)s)
          AND (is_new = 'Y' OR is_new IS NULL OR out_date IS NULL)
    """
    rows = _query(sql, {
        "hs300": HS300_INDEX,
        "sz50": SZ50_INDEX,
        "zz500": ZZ500_INDEX,
    })

    for idx_code, con_code in rows:
        if idx_code == HS300_INDEX:
            result["hs300"].add(con_code)
        elif idx_code == SZ50_INDEX:
            result["sz50"].add(con_code)
        elif idx_code == ZZ500_INDEX:
            result["zz500"].add(con_code)

    logger.info(
        f"Index members loaded: HS300={len(result['hs300'])}, "
        f"SZ50={len(result['sz50'])}, ZZ500={len(result['zz500'])}"
    )
    return result


def _fetch_concept_members() -> dict[str, list[str]]:
    """Return {ts_code: [concept_board_code, ...]} from ods_ths_member.

    Note: ods_ths_member schema has `ts_code` as the concept board code
    and `code` as the stock code. We invert to {stock_code: [concepts]}.
    """
    result: dict[str, list[str]] = {}
    sql = """
        SELECT code AS stock_code, ts_code AS concept_code, name AS concept_name
        FROM ods_ths_member FINAL
        WHERE (is_new = 'Y' OR is_new IS NULL OR out_date IS NULL)
    """
    rows = _query(sql)

    for stock_code, concept_code, _concept_name in rows:
        if not stock_code:
            continue
        result.setdefault(stock_code, []).append(concept_code)

    logger.info(f"Concept members loaded for {len(result)} stocks")
    return result


def _fetch_concept_names() -> dict[str, str]:
    """Return {concept_code: concept_name} for THS concept boards.

    We query distinct concept boards from ods_ths_member.
    """
    sql = """
        SELECT DISTINCT ts_code, any(name) AS name
        FROM ods_ths_member FINAL
        GROUP BY ts_code
    """
    rows = _query(sql)
    return {code: name for code, name in rows if code and name}


def _fetch_daily_basic_latest() -> dict[str, dict]:
    """Latest daily_basic per stock."""
    sql = """
        SELECT ts_code,
               argMax(total_mv, trade_date) AS total_mv,
               argMax(circ_mv, trade_date) AS circ_mv,
               argMax(pe_ttm, trade_date) AS pe_ttm,
               argMax(pb, trade_date) AS pb,
               argMax(dv_ratio, trade_date) AS dv_ratio,
               argMax(turnover_rate, trade_date) AS turnover_rate,
               argMax(close, trade_date) AS close
        FROM ods_daily_basic
        WHERE trade_date >= today() - 30
        GROUP BY ts_code
    """
    rows = _query(sql)
    result = {}
    for r in rows:
        result[r[0]] = {
            "total_mv": r[1],
            "circ_mv": r[2],
            "pe_ttm": r[3],
            "pb": r[4],
            "dv_ratio": r[5],
            "turnover_rate": r[6],
            "close": r[7],
        }
    logger.info(f"Daily basic loaded for {len(result)} stocks")
    return result


def _fetch_fina_indicator_latest() -> dict[str, dict]:
    """Latest fina_indicator per stock."""
    sql = """
        SELECT ts_code,
               argMax(roe, end_date) AS roe,
               argMax(roa, end_date) AS roa,
               argMax(gross_profit_margin, end_date) AS gross_profit_margin,
               argMax(net_profit_margin, end_date) AS net_profit_margin,
               argMax(debt_to_assets, end_date) AS debt_to_assets,
               argMax(eps, end_date) AS eps
        FROM ods_fina_indicator
        GROUP BY ts_code
    """
    rows = _query(sql)
    result = {}
    for r in rows:
        result[r[0]] = {
            "roe": r[1],
            "roa": r[2],
            "gross_profit_margin": r[3],
            "net_profit_margin": r[4],
            "debt_to_assets": r[5],
            "eps": r[6],
        }
    logger.info(f"Fina indicator loaded for {len(result)} stocks")
    return result


def _fetch_stock_company() -> dict[str, dict]:
    """Company info per stock."""
    sql = """
        SELECT ts_code, com_name, province, city, employees,
               setup_date, main_business, business_scope
        FROM ods_stock_company FINAL
    """
    rows = _query(sql)
    result = {}
    for r in rows:
        result[r[0]] = {
            "com_name": r[1],
            "province": r[2],
            "city": r[3],
            "employees": r[4],
            "setup_date": str(r[5]) if r[5] else None,
            "main_business": r[6],
            "business_scope": r[7],
        }
    logger.info(f"Stock company loaded for {len(result)} stocks")
    return result


def _fetch_stock_basic() -> list[dict]:
    """Basic info for all A-share stocks."""
    sql = """
        SELECT ts_code, name, industry, area, market, list_date, list_status
        FROM ods_stock_basic FINAL
        WHERE list_status = 'L'
    """
    rows = _query(sql)
    result = []
    for r in rows:
        result.append({
            "ts_code": r[0],
            "name": r[1],
            "industry": r[2],
            "area": r[3],
            "market": r[4],
            "list_date": str(r[5]) if r[5] else None,
        })
    logger.info(f"Stock basic loaded: {len(result)} active stocks")
    return result


def build_stock_matrix() -> dict[str, dict[str, Any]]:
    """Build the full stock attribute matrix by joining 6 tables.

    Returns: {ts_code: {name, industry, ..., concepts: [...], in_hs300: bool, ...}}
    """
    t0 = time.time()

    # Load all source tables in parallel (sequential calls but each is a single bulk query)
    basics = _fetch_stock_basic()
    companies = _fetch_stock_company()
    daily = _fetch_daily_basic_latest()
    fina = _fetch_fina_indicator_latest()
    indices = _fetch_index_members()
    concept_map = _fetch_concept_members()
    concept_names = _fetch_concept_names()

    matrix: dict[str, dict[str, Any]] = {}
    for b in basics:
        ts_code = b["ts_code"]
        c = companies.get(ts_code, {})
        d = daily.get(ts_code, {})
        f = fina.get(ts_code, {})

        # Resolve concept codes to human-readable names
        concept_codes = concept_map.get(ts_code, [])
        concepts = [concept_names.get(code, code) for code in concept_codes]

        matrix[ts_code] = {
            # Basic
            "ts_code": ts_code,
            "name": b["name"],
            "industry": b["industry"],
            "area": b["area"],
            "market": b["market"],  # 主板/中小板/创业板/科创板
            "list_date": b["list_date"],

            # Company
            "province": c.get("province"),
            "city": c.get("city"),
            "employees": c.get("employees"),
            "main_business": c.get("main_business"),

            # Daily basic
            "total_mv": d.get("total_mv"),  # 万元
            "pe_ttm": d.get("pe_ttm"),
            "pb": d.get("pb"),
            "dv_ratio": d.get("dv_ratio"),
            "turnover_rate": d.get("turnover_rate"),
            "close": d.get("close"),

            # Fina indicator
            "roe": f.get("roe"),
            "net_profit_margin": f.get("net_profit_margin"),
            "gross_profit_margin": f.get("gross_profit_margin"),
            "debt_to_assets": f.get("debt_to_assets"),

            # Index membership
            "in_hs300": ts_code in indices["hs300"],
            "in_sz50": ts_code in indices["sz50"],
            "in_zz500": ts_code in indices["zz500"],

            # Concepts (human-readable names)
            "concepts": concepts,
        }

    elapsed = time.time() - t0
    logger.info(
        f"Stock matrix built: {len(matrix)} stocks in {elapsed:.1f}s "
        f"(with {sum(1 for v in matrix.values() if v['concepts'])} having concepts)"
    )
    return matrix


def get_stock_matrix(force_rebuild: bool = False) -> dict[str, dict[str, Any]]:
    """Get the stock matrix, using Redis cache when available.

    Args:
        force_rebuild: If True, bypass cache and rebuild from scratch.

    Returns:
        dict mapping ts_code -> attribute dict
    """
    cache = get_cache_service()

    if not force_rebuild:
        cached = cache.get(CACHE_KEY)
        if cached:
            try:
                matrix = json.loads(cached) if isinstance(cached, str) else cached
                if isinstance(matrix, dict) and matrix:
                    logger.debug(f"Stock matrix cache hit: {len(matrix)} stocks")
                    return matrix
            except Exception as e:
                logger.warning(f"Failed to parse cached matrix: {e}")

    matrix = build_stock_matrix()
    if matrix:
        try:
            cache.set(CACHE_KEY, json.dumps(matrix), ttl=CACHE_TTL_SECONDS)
            logger.info(f"Stock matrix cached: {len(matrix)} stocks, TTL 24h")
        except Exception as e:
            logger.warning(f"Failed to cache matrix: {e}")

    return matrix


def invalidate_cache() -> None:
    """Manually invalidate the stock matrix cache."""
    cache = get_cache_service()
    cache.delete(CACHE_KEY)
    logger.info("Stock matrix cache invalidated")
