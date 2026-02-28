"""Full-market financial screening engine.

Core constraint: ONLY reads from ClickHouse local data. NEVER calls any TuShare plugin.
Returns detailed per-rule execution stats for frontend display.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from stock_datasource.models.database import db_client

from .benford_checker import check_benford_for_stock
from .data_readiness import get_data_readiness_checker
from .schemas import (
    DataReadinessResult,
    RuleExecutionDetail,
    ScreeningResult,
    ScreeningResultItem,
    ScreeningRule,
)

logger = logging.getLogger(__name__)


def default_screening_rules() -> list[ScreeningRule]:
    """Return default screening rules."""
    return [
        ScreeningRule(
            name="revenue_growth_2y",
            category="traditional",
            description="连续两年营收增长率 > 0",
            params={"min_growth": 0, "years": 2},
        ),
        ScreeningRule(
            name="net_profit_positive",
            category="traditional",
            description="近一年净利润 > 0",
            params={},
        ),
        ScreeningRule(
            name="roe_3y_avg",
            category="traditional",
            description="近三年平均ROE >= 5%",
            params={"min_roe": 5.0, "years": 3},
        ),
        ScreeningRule(
            name="cashflow_sync",
            category="custom",
            description="经营现金流同步率 > 0.5，连续两年",
            params={"min_ratio": 0.5, "years": 2},
        ),
        ScreeningRule(
            name="expense_anomaly",
            category="custom",
            description="费用率年度波动 < 50%",
            params={"max_volatility": 50.0},
        ),
        ScreeningRule(
            name="receivable_revenue_gap",
            category="custom",
            description="应收账款增速 - 营收增速 < 20%",
            params={"max_gap": 20.0},
        ),
        ScreeningRule(
            name="benford_check",
            category="benford",
            description="本福德首位数字定律检验(软条件)",
            params={"p_threshold": 0.05},
            is_hard_reject=False,
        ),
    ]


class ScreeningEngine:
    """Full-market financial screening engine.

    ONLY reads from ClickHouse. Each rule returns RuleExecutionDetail for frontend.
    """

    def __init__(self, rules: Optional[list[ScreeningRule]] = None):
        self.rules = rules or default_screening_rules()
        self.readiness_checker = get_data_readiness_checker()

    async def run_screening(self, trade_date: Optional[str] = None) -> ScreeningResult:
        """Run full-market screening.

        1. Check data readiness
        2. If missing -> return result with data_readiness report
        3. If ready -> execute each rule, collect stats
        4. Return complete result for frontend display
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        run_date = trade_date or datetime.now().strftime("%Y%m%d")

        # Step 1: Check data readiness
        readiness = await self.readiness_checker.check_screening_readiness()
        if not readiness.is_ready:
            return ScreeningResult(
                run_date=run_date,
                run_id=run_id,
                data_readiness=readiness,
                status="data_missing",
            )

        # Step 2: Load financial data from ClickHouse
        try:
            fina_df = self._load_fina_data()
            income_df = self._load_income_data()
            balance_df = self._load_balance_data()
            cashflow_df = self._load_cashflow_data()
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return ScreeningResult(
                run_date=run_date,
                run_id=run_id,
                data_readiness=readiness,
                status="error",
            )

        # Get unique stock list
        all_ts_codes = set()
        if len(fina_df) > 0:
            all_ts_codes.update(fina_df["ts_code"].unique())

        if not all_ts_codes:
            return ScreeningResult(
                run_date=run_date,
                run_id=run_id,
                data_readiness=readiness,
                status="error",
            )

        # Step 3: Execute rules
        stock_results: dict[str, dict] = {
            code: {"ts_code": code, "pass": True, "reject_reasons": [], "rule_details": []}
            for code in all_ts_codes
        }

        rule_execution_details: list[RuleExecutionDetail] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            rule_start = time.time()
            detail = RuleExecutionDetail(
                rule_name=rule.name,
                category=rule.category,
                enabled=True,
                total_checked=len(all_ts_codes),
                threshold=rule.description,
            )

            try:
                if rule.name == "revenue_growth_2y":
                    passed, failed, skipped = self._check_revenue_growth(
                        fina_df, all_ts_codes, rule.params
                    )
                elif rule.name == "net_profit_positive":
                    passed, failed, skipped = self._check_net_profit(
                        income_df, all_ts_codes
                    )
                elif rule.name == "roe_3y_avg":
                    passed, failed, skipped = self._check_roe(
                        fina_df, all_ts_codes, rule.params
                    )
                elif rule.name == "cashflow_sync":
                    passed, failed, skipped = self._check_cashflow_sync(
                        income_df, cashflow_df, all_ts_codes, rule.params
                    )
                elif rule.name == "expense_anomaly":
                    passed, failed, skipped = self._check_expense_anomaly(
                        income_df, all_ts_codes, rule.params
                    )
                elif rule.name == "receivable_revenue_gap":
                    passed, failed, skipped = self._check_receivable_revenue(
                        income_df, balance_df, all_ts_codes, rule.params
                    )
                elif rule.name == "benford_check":
                    passed, failed, skipped = self._check_benford(
                        income_df, all_ts_codes, rule.params
                    )
                else:
                    continue

                detail.passed_count = len(passed)
                detail.rejected_count = len(failed)
                detail.skipped_count = len(skipped)
                detail.execution_time_ms = int((time.time() - rule_start) * 1000)
                detail.sample_rejects = [
                    {"ts_code": code, "reason": f"未通过{rule.description}"}
                    for code in list(failed)[:5]
                ]

                # Apply rejections
                if rule.is_hard_reject:
                    for code in failed:
                        if code in stock_results:
                            stock_results[code]["pass"] = False
                            stock_results[code]["reject_reasons"].append(rule.description)

                # Record rule detail on each stock
                for code in all_ts_codes:
                    if code in stock_results:
                        stock_results[code]["rule_details"].append({
                            "rule_name": rule.name,
                            "passed": code in passed,
                            "skipped": code in skipped,
                        })

            except Exception as e:
                logger.error(f"Rule {rule.name} execution error: {e}")
                detail.skipped_count = len(all_ts_codes)

            rule_execution_details.append(detail)

        # Step 4: Build result
        passed_stocks = []
        rejected_stocks = []
        stock_names = self._load_stock_names()

        for code, result in stock_results.items():
            name = stock_names.get(code, "")
            item = ScreeningResultItem(
                ts_code=code,
                stock_name=name,
                overall_pass=result["pass"],
                reject_reasons=result["reject_reasons"],
                rule_details=result["rule_details"],
            )
            if result["pass"]:
                passed_stocks.append(item)
            else:
                rejected_stocks.append(item)

        elapsed_ms = int((time.time() - start_time) * 1000)

        screening_result = ScreeningResult(
            run_date=run_date,
            run_id=run_id,
            total_stocks=len(all_ts_codes),
            passed_count=len(passed_stocks),
            rejected_count=len(rejected_stocks),
            passed_stocks=passed_stocks,
            rejected_stocks=rejected_stocks[:500],  # Limit for response size
            rule_details=rule_execution_details,
            data_readiness=readiness,
            execution_time_ms=elapsed_ms,
            status="success",
        )

        # Persist results
        self._save_results(screening_result)

        return screening_result

    # =========================================================================
    # Rule Implementations (all read from local DataFrames, no remote calls)
    # =========================================================================

    def _check_revenue_growth(
        self, fina_df: pd.DataFrame, ts_codes: set, params: dict
    ) -> tuple[set, set, set]:
        """Revenue growth > 0 for consecutive years."""
        passed, failed, skipped = set(), set(), set()
        min_growth = params.get("min_growth", 0)
        years = params.get("years", 2)

        if "revenue_yoy" not in fina_df.columns:
            return set(), set(), ts_codes

        for code in ts_codes:
            stock_data = fina_df[fina_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            if len(stock_data) < years:
                skipped.add(code)
                continue

            recent = stock_data.head(years)
            growth_values = pd.to_numeric(recent["revenue_yoy"], errors="coerce")
            if growth_values.isna().any():
                skipped.add(code)
            elif (growth_values > min_growth).all():
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    def _check_net_profit(
        self, income_df: pd.DataFrame, ts_codes: set
    ) -> tuple[set, set, set]:
        """Net profit > 0 for the latest period."""
        passed, failed, skipped = set(), set(), set()

        if "n_income" not in income_df.columns:
            return set(), set(), ts_codes

        for code in ts_codes:
            stock_data = income_df[income_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            if len(stock_data) == 0:
                skipped.add(code)
                continue

            latest_profit = pd.to_numeric(stock_data.iloc[0].get("n_income", None), errors="coerce")
            if pd.isna(latest_profit):
                skipped.add(code)
            elif latest_profit > 0:
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    def _check_roe(
        self, fina_df: pd.DataFrame, ts_codes: set, params: dict
    ) -> tuple[set, set, set]:
        """Average ROE >= min_roe over N years."""
        passed, failed, skipped = set(), set(), set()
        min_roe = params.get("min_roe", 5.0)
        years = params.get("years", 3)

        if "roe" not in fina_df.columns:
            return set(), set(), ts_codes

        for code in ts_codes:
            stock_data = fina_df[fina_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            if len(stock_data) < years:
                skipped.add(code)
                continue

            recent = stock_data.head(years)
            roe_values = pd.to_numeric(recent["roe"], errors="coerce")
            if roe_values.isna().any():
                skipped.add(code)
            elif roe_values.mean() >= min_roe:
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    def _check_cashflow_sync(
        self, income_df: pd.DataFrame, cashflow_df: pd.DataFrame,
        ts_codes: set, params: dict,
    ) -> tuple[set, set, set]:
        """Cashflow sync ratio: operating_cf / (revenue + expense) > threshold."""
        passed, failed, skipped = set(), set(), set()
        min_ratio = params.get("min_ratio", 0.5)
        years = params.get("years", 2)

        for code in ts_codes:
            inc_data = income_df[income_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            cf_data = cashflow_df[cashflow_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )

            if len(inc_data) < years or len(cf_data) < years:
                skipped.add(code)
                continue

            ok_count = 0
            for i in range(min(years, len(inc_data), len(cf_data))):
                revenue = pd.to_numeric(inc_data.iloc[i].get("total_revenue", 0), errors="coerce")
                cashflow = pd.to_numeric(cf_data.iloc[i].get("n_cashflow_act", 0), errors="coerce")

                if pd.isna(revenue) or pd.isna(cashflow) or revenue == 0:
                    continue
                ratio = cashflow / abs(revenue)
                if ratio > min_ratio:
                    ok_count += 1

            if ok_count >= years:
                passed.add(code)
            elif ok_count == 0 and len(inc_data) >= years:
                failed.add(code)
            else:
                skipped.add(code)

        return passed, failed, skipped

    def _check_expense_anomaly(
        self, income_df: pd.DataFrame, ts_codes: set, params: dict
    ) -> tuple[set, set, set]:
        """Detect abnormal expense ratio volatility."""
        passed, failed, skipped = set(), set(), set()
        max_vol = params.get("max_volatility", 50.0)

        for code in ts_codes:
            stock_data = income_df[income_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            if len(stock_data) < 2:
                skipped.add(code)
                continue

            revenues = pd.to_numeric(stock_data["total_revenue"], errors="coerce")
            if revenues.isna().all() or (revenues == 0).all():
                skipped.add(code)
                continue

            # Calculate total expense ratio if columns exist
            expense_cols = ["sell_exp", "admin_exp", "rd_exp"]
            available_cols = [c for c in expense_cols if c in stock_data.columns]

            if not available_cols:
                passed.add(code)
                continue

            expenses = stock_data[available_cols].apply(
                pd.to_numeric, errors="coerce"
            ).sum(axis=1)
            ratios = expenses / revenues.replace(0, np.nan)
            ratios = ratios.dropna()

            if len(ratios) < 2:
                skipped.add(code)
                continue

            volatility = ratios.std() / ratios.mean() * 100 if ratios.mean() != 0 else 0
            if volatility < max_vol:
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    def _check_receivable_revenue(
        self, income_df: pd.DataFrame, balance_df: pd.DataFrame,
        ts_codes: set, params: dict,
    ) -> tuple[set, set, set]:
        """Receivable growth - Revenue growth < max_gap."""
        passed, failed, skipped = set(), set(), set()
        max_gap = params.get("max_gap", 20.0)

        for code in ts_codes:
            inc_data = income_df[income_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )
            bal_data = balance_df[balance_df["ts_code"] == code].sort_values(
                "end_date", ascending=False
            )

            if len(inc_data) < 2 or len(bal_data) < 2:
                skipped.add(code)
                continue

            # Revenue growth
            rev_curr = pd.to_numeric(inc_data.iloc[0].get("total_revenue", 0), errors="coerce")
            rev_prev = pd.to_numeric(inc_data.iloc[1].get("total_revenue", 0), errors="coerce")

            # Receivable growth
            recv_curr = pd.to_numeric(bal_data.iloc[0].get("accounts_receiv", 0), errors="coerce")
            recv_prev = pd.to_numeric(bal_data.iloc[1].get("accounts_receiv", 0), errors="coerce")

            if pd.isna(rev_prev) or rev_prev == 0 or pd.isna(recv_prev) or recv_prev == 0:
                skipped.add(code)
                continue

            rev_growth = ((rev_curr - rev_prev) / abs(rev_prev)) * 100
            recv_growth = ((recv_curr - recv_prev) / abs(recv_prev)) * 100
            gap = recv_growth - rev_growth

            if gap < max_gap:
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    def _check_benford(
        self, income_df: pd.DataFrame, ts_codes: set, params: dict
    ) -> tuple[set, set, set]:
        """Benford's first-digit law check (soft condition)."""
        passed, failed, skipped = set(), set(), set()
        p_threshold = params.get("p_threshold", 0.05)

        for code in ts_codes:
            stock_data = income_df[income_df["ts_code"] == code]
            if len(stock_data) < 4:
                skipped.add(code)
                continue

            revenue = pd.to_numeric(stock_data.get("total_revenue", pd.Series()), errors="coerce")
            profit = pd.to_numeric(stock_data.get("n_income", pd.Series()), errors="coerce")

            result = check_benford_for_stock(revenue, profit, p_threshold)
            if result["pass"]:
                passed.add(code)
            else:
                failed.add(code)

        return passed, failed, skipped

    # =========================================================================
    # Data Loading (ClickHouse only)
    # =========================================================================

    def _load_fina_data(self) -> pd.DataFrame:
        """Load financial indicator data from ClickHouse."""
        try:
            return db_client.execute_query(
                """SELECT ts_code, end_date,
                       argMax(roe, _ingested_at) as roe,
                       argMax(revenue_yoy, _ingested_at) as revenue_yoy,
                       argMax(netprofit_yoy, _ingested_at) as netprofit_yoy
                FROM fact_fina_indicator
                WHERE end_date >= '20200101'
                GROUP BY ts_code, end_date
                ORDER BY ts_code, end_date DESC"""
            )
        except Exception as e:
            logger.error(f"Failed to load fina data: {e}")
            return pd.DataFrame()

    def _load_income_data(self) -> pd.DataFrame:
        """Load income statement data from ClickHouse."""
        try:
            cols = "ts_code, end_date, total_revenue, n_income"
            optional_cols = ["sell_exp", "admin_exp", "rd_exp"]
            # Try to include optional columns
            for col in optional_cols:
                cols += f", {col}"

            return db_client.execute_query(
                f"""SELECT {cols}
                FROM fact_income
                WHERE end_date >= '20200101'
                ORDER BY ts_code, end_date DESC"""
            )
        except Exception:
            # Fallback without optional columns
            try:
                return db_client.execute_query(
                    """SELECT ts_code, end_date, total_revenue, n_income
                    FROM fact_income
                    WHERE end_date >= '20200101'
                    ORDER BY ts_code, end_date DESC"""
                )
            except Exception as e:
                logger.error(f"Failed to load income data: {e}")
                return pd.DataFrame()

    def _load_balance_data(self) -> pd.DataFrame:
        """Load balance sheet data from ClickHouse."""
        try:
            return db_client.execute_query(
                """SELECT ts_code, end_date, accounts_receiv
                FROM fact_balancesheet
                WHERE end_date >= '20200101'
                ORDER BY ts_code, end_date DESC"""
            )
        except Exception as e:
            logger.error(f"Failed to load balance data: {e}")
            return pd.DataFrame()

    def _load_cashflow_data(self) -> pd.DataFrame:
        """Load cashflow data from ClickHouse."""
        try:
            return db_client.execute_query(
                """SELECT ts_code, end_date, n_cashflow_act
                FROM fact_cashflow
                WHERE end_date >= '20200101'
                ORDER BY ts_code, end_date DESC"""
            )
        except Exception as e:
            logger.error(f"Failed to load cashflow data: {e}")
            return pd.DataFrame()

    def _load_stock_names(self) -> dict[str, str]:
        """Load stock name mapping."""
        try:
            df = db_client.execute_query(
                "SELECT ts_code, name FROM dim_stock_basic"
            )
            return dict(zip(df["ts_code"], df["name"]))
        except Exception:
            return {}

    def _save_results(self, result: ScreeningResult) -> None:
        """Persist screening results and run stats to ClickHouse."""
        try:
            # Save run stats
            stats_data = {
                "run_date": result.run_date,
                "run_id": result.run_id,
                "total_stocks": result.total_stocks,
                "passed_count": result.passed_count,
                "rejected_count": result.rejected_count,
                "rule_stats": json.dumps(
                    [d.model_dump() for d in result.rule_details], ensure_ascii=False
                ),
                "data_readiness": result.data_readiness.model_dump_json() if result.data_readiness else "",
                "execution_time_ms": result.execution_time_ms,
                "status": result.status,
            }
            stats_df = pd.DataFrame([stats_data])
            db_client.insert_dataframe("quant_screening_run_stats", stats_df)

            # Save individual stock results (passed only to save space)
            if result.passed_stocks:
                rows = []
                for stock in result.passed_stocks:
                    rows.append({
                        "run_date": result.run_date,
                        "run_id": result.run_id,
                        "ts_code": stock.ts_code,
                        "stock_name": stock.stock_name,
                        "overall_pass": 1,
                        "reject_reasons": stock.reject_reasons,
                        "rule_details": json.dumps(stock.rule_details, ensure_ascii=False),
                    })
                if rows:
                    df = pd.DataFrame(rows)
                    db_client.insert_dataframe("quant_screening_result", df)

        except Exception as e:
            logger.error(f"Failed to save screening results: {e}")


# Singleton
_screening_engine: Optional[ScreeningEngine] = None


def get_screening_engine() -> ScreeningEngine:
    global _screening_engine
    if _screening_engine is None:
        _screening_engine = ScreeningEngine()
    return _screening_engine
