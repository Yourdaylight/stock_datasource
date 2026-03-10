"""Financial Analysis Service - company listing, report browsing, AI analysis persistence."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FinancialAnalysisService:
    """Service for financial analysis module: company list, report periods, analysis CRUD."""

    def __init__(self):
        self._db = None
        self._financial_service = None
        self._hk_financial_service = None

    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            from stock_datasource.models.database import db_client
            self._db = db_client
        return self._db

    @property
    def financial_service(self):
        """Lazy load A-share financial report service."""
        if self._financial_service is None:
            from stock_datasource.services.financial_report_service import FinancialReportService
            self._financial_service = FinancialReportService()
        return self._financial_service

    @property
    def hk_financial_service(self):
        """Lazy load HK financial report service."""
        if self._hk_financial_service is None:
            from stock_datasource.services.hk_financial_report_service import HKFinancialReportService
            self._hk_financial_service = HKFinancialReportService()
        return self._hk_financial_service

    # ========== Company List ==========

    def get_companies(
        self,
        market: str = "A",
        keyword: str = "",
        industry: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get paginated company list with search and filter.

        Args:
            market: 'A' for A-share, 'HK' for Hong Kong
            keyword: Search by code or name
            industry: Filter by industry
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Dict with items, total, page, page_size
        """
        try:
            offset = (page - 1) * page_size

            if market == "HK":
                return self._get_hk_companies(keyword, industry, page, page_size, offset)

            # A-share: query ods_stock_basic
            where_clauses = ["list_status = 'L'"]
            params = {}

            if keyword:
                where_clauses.append(
                    "(ts_code ILIKE %(kw)s OR name ILIKE %(kw)s OR symbol ILIKE %(kw)s)"
                )
                params["kw"] = f"%{keyword}%"

            if industry:
                where_clauses.append("industry = %(industry)s")
                params["industry"] = industry

            where_sql = " AND ".join(where_clauses)

            # Count
            count_sql = f"SELECT count() FROM ods_stock_basic FINAL WHERE {where_sql}"
            count_result = self.db.execute(count_sql, params)
            total = count_result[0][0] if count_result else 0

            # Query
            query_sql = f"""
                SELECT ts_code, symbol, name, area, industry, market, list_date
                FROM ods_stock_basic FINAL
                WHERE {where_sql}
                ORDER BY ts_code ASC
                LIMIT %(limit)s OFFSET %(offset)s
            """
            params["limit"] = page_size
            params["offset"] = offset

            rows = self.db.execute(query_sql, params)

            items = []
            for row in rows:
                list_date_val = row[6]
                if hasattr(list_date_val, "strftime"):
                    list_date_val = list_date_val.strftime("%Y-%m-%d")
                items.append({
                    "ts_code": row[0],
                    "symbol": row[1],
                    "name": row[2],
                    "area": row[3] or "",
                    "industry": row[4] or "",
                    "market": row[5] or "",
                    "list_date": str(list_date_val) if list_date_val else "",
                })

            return {
                "status": "success",
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            logger.error(f"Error getting companies: {e}")
            return {"status": "error", "error": str(e), "items": [], "total": 0}

    def _get_hk_companies(
        self, keyword: str, industry: str, page: int, page_size: int, offset: int
    ) -> Dict[str, Any]:
        """Get HK stock companies from available HK tables."""
        try:
            # Query distinct HK stocks from fina_indicator table
            where_clauses = ["1=1"]
            params = {}

            if keyword:
                where_clauses.append("ts_code ILIKE %(kw)s")
                params["kw"] = f"%{keyword}%"

            where_sql = " AND ".join(where_clauses)

            count_sql = f"""
                SELECT count(DISTINCT ts_code) 
                FROM ods_hk_fina_indicator FINAL 
                WHERE {where_sql}
            """
            count_result = self.db.execute(count_sql, params)
            total = count_result[0][0] if count_result else 0

            query_sql = f"""
                SELECT 
                    ts_code,
                    replaceAll(ts_code, '.HK', '') AS symbol,
                    any(name) AS name,
                    '' AS area,
                    '' AS industry,
                    'HK' AS market,
                    '' AS list_date
                FROM ods_hk_fina_indicator FINAL
                WHERE {where_sql}
                GROUP BY ts_code
                ORDER BY ts_code ASC
                LIMIT %(limit)s OFFSET %(offset)s
            """
            params["limit"] = page_size
            params["offset"] = offset

            rows = self.db.execute(query_sql, params)

            items = []
            for row in rows:
                items.append({
                    "ts_code": row[0],
                    "symbol": row[1],
                    "name": row[2],
                    "area": row[3] or "",
                    "industry": row[4] or "",
                    "market": row[5] or "HK",
                    "list_date": row[6] or "",
                })

            return {
                "status": "success",
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            logger.error(f"Error getting HK companies: {e}")
            return {"status": "error", "error": str(e), "items": [], "total": 0}

    def get_industries(self, market: str = "A") -> Dict[str, Any]:
        """Get distinct industry list for filter dropdown."""
        try:
            if market == "HK":
                return {"status": "success", "industries": []}

            query = """
                SELECT DISTINCT industry
                FROM ods_stock_basic FINAL
                WHERE list_status = 'L' AND industry != '' AND industry IS NOT NULL
                ORDER BY industry ASC
            """
            rows = self.db.execute(query)
            industries = [row[0] for row in rows if row[0]]
            return {"status": "success", "industries": industries}
        except Exception as e:
            logger.error(f"Error getting industries: {e}")
            return {"status": "error", "error": str(e), "industries": []}

    # ========== Report Period List ==========

    def get_report_periods(
        self, ts_code: str, market: str = "A"
    ) -> Dict[str, Any]:
        """Get all report periods for a company with core indicators summary.

        Args:
            ts_code: Stock code (e.g. '000001.SZ' or '00700.HK')
            market: 'A' or 'HK'

        Returns:
            Dict with company info and report periods list
        """
        try:
            if market == "HK":
                return self._get_hk_report_periods(ts_code)

            # Get company basic info
            company_info = self._get_company_info(ts_code, market)

            # Query report periods from fina_indicator
            query = """
                SELECT 
                    end_date,
                    anyIf(roe, roe IS NOT NULL AND toString(roe) != '\\\\N') AS roe,
                    anyIf(gross_profit_margin, gross_profit_margin IS NOT NULL AND toString(gross_profit_margin) != '\\\\N') AS gross_margin,
                    anyIf(net_profit_margin, net_profit_margin IS NOT NULL AND toString(net_profit_margin) != '\\\\N') AS net_margin,
                    anyIf(eps, eps IS NOT NULL AND toString(eps) != '\\\\N') AS eps,
                    anyIf(current_ratio, current_ratio IS NOT NULL AND toString(current_ratio) != '\\\\N') AS current_ratio,
                    anyIf(debt_to_assets, debt_to_assets IS NOT NULL AND toString(debt_to_assets) != '\\\\N') AS debt_ratio
                FROM ods_fina_indicator FINAL
                WHERE ts_code = %(ts_code)s
                GROUP BY end_date
                ORDER BY end_date DESC
            """
            rows = self.db.execute(query, {"ts_code": ts_code})

            # Also get revenue and net_profit from income statement
            income_query = """
                SELECT 
                    end_date,
                    anyIf(revenue, revenue IS NOT NULL) AS revenue,
                    anyIf(n_income_attr_p, n_income_attr_p IS NOT NULL) AS net_profit
                FROM ods_income_statement FINAL
                WHERE ts_code = %(ts_code)s AND report_type = '1'
                GROUP BY end_date
                ORDER BY end_date DESC
            """
            income_rows = self.db.execute(income_query, {"ts_code": ts_code})
            income_map = {}
            for ir in income_rows:
                income_map[str(ir[0])] = {"revenue": ir[1], "net_profit": ir[2]}

            # Check analysis status for each period
            analysis_status = self._get_analysis_status_map(ts_code)

            periods = []
            for row in rows:
                end_date = str(row[0])
                income_info = income_map.get(end_date, {})
                report_type = self._classify_report_type(end_date)

                periods.append({
                    "end_date": end_date,
                    "report_type": report_type,
                    "report_type_label": self._report_type_label(report_type),
                    "revenue": self._safe_float(income_info.get("revenue")),
                    "net_profit": self._safe_float(income_info.get("net_profit")),
                    "roe": self._safe_float(row[1]),
                    "gross_margin": self._safe_float(row[2]),
                    "net_margin": self._safe_float(row[3]),
                    "eps": self._safe_float(row[4]),
                    "current_ratio": self._safe_float(row[5]),
                    "debt_ratio": self._safe_float(row[6]),
                    "has_analysis": analysis_status.get(end_date, False),
                })

            return {
                "status": "success",
                "company": company_info,
                "periods": periods,
            }
        except Exception as e:
            logger.error(f"Error getting report periods for {ts_code}: {e}")
            return {"status": "error", "error": str(e), "company": {}, "periods": []}

    def _get_hk_report_periods(self, ts_code: str) -> Dict[str, Any]:
        """Get HK stock report periods."""
        try:
            company_info = self._get_company_info(ts_code, "HK")

            query = """
                SELECT 
                    end_date,
                    anyIf(roe_avg, roe_avg IS NOT NULL AND toString(roe_avg) != '\\\\N') AS roe,
                    anyIf(gross_profit_ratio, gross_profit_ratio IS NOT NULL AND toString(gross_profit_ratio) != '\\\\N') AS gross_margin,
                    anyIf(net_profit_ratio, net_profit_ratio IS NOT NULL AND toString(net_profit_ratio) != '\\\\N') AS net_margin,
                    anyIf(basic_eps, basic_eps IS NOT NULL AND toString(basic_eps) != '\\\\N') AS eps
                FROM ods_hk_fina_indicator FINAL
                WHERE ts_code = %(ts_code)s
                GROUP BY end_date
                ORDER BY end_date DESC
            """
            rows = self.db.execute(query, {"ts_code": ts_code})

            # HK income for revenue/net_profit (ods_hk_income uses row-based ind_name/ind_value)
            income_query = """
                SELECT 
                    end_date,
                    anyIf(toFloat64OrNull(ind_value), ind_name = 'revenue') AS revenue,
                    anyIf(toFloat64OrNull(ind_value), ind_name = 'net_profit' OR ind_name = 'n_income') AS net_profit
                FROM ods_hk_income FINAL
                WHERE ts_code = %(ts_code)s
                GROUP BY end_date
                ORDER BY end_date DESC
            """
            income_rows = self.db.execute(income_query, {"ts_code": ts_code})
            income_map = {}
            for ir in income_rows:
                income_map[str(ir[0])] = {"revenue": ir[1], "net_profit": ir[2]}

            analysis_status = self._get_analysis_status_map(ts_code)

            periods = []
            for row in rows:
                end_date = str(row[0])
                income_info = income_map.get(end_date, {})
                report_type = self._classify_report_type(end_date)

                periods.append({
                    "end_date": end_date,
                    "report_type": report_type,
                    "report_type_label": self._report_type_label(report_type),
                    "revenue": self._safe_float(income_info.get("revenue")),
                    "net_profit": self._safe_float(income_info.get("net_profit")),
                    "roe": self._safe_float(row[1]),
                    "gross_margin": self._safe_float(row[2]),
                    "net_margin": self._safe_float(row[3]),
                    "eps": self._safe_float(row[4]),
                    "current_ratio": None,
                    "debt_ratio": None,
                    "has_analysis": analysis_status.get(end_date, False),
                })

            return {
                "status": "success",
                "company": company_info,
                "periods": periods,
            }
        except Exception as e:
            logger.error(f"Error getting HK report periods for {ts_code}: {e}")
            return {"status": "error", "error": str(e), "company": {}, "periods": []}

    # ========== Report Detail ==========

    def get_report_detail(
        self, ts_code: str, end_date: str, market: str = "A"
    ) -> Dict[str, Any]:
        """Get detailed financial report for a specific period.

        Reuses existing FinancialReportService / HKFinancialReportService.
        """
        try:
            if market == "HK":
                analysis = self.hk_financial_service.get_comprehensive_analysis(ts_code, 8)
            else:
                analysis = self.financial_service.get_comprehensive_analysis(ts_code, 12)

            if analysis.get("status") == "error":
                return analysis

            # Get company info
            company_info = self._get_company_info(ts_code, market)

            # Get the specific period's data from the analysis
            # Also include full statements for the period
            if market == "HK":
                statements = self._get_hk_statements(ts_code, end_date)
            else:
                statements = self._get_a_statements(ts_code, end_date)

            return {
                "status": "success",
                "company": company_info,
                "end_date": end_date,
                "report_type": self._classify_report_type(end_date),
                "report_type_label": self._report_type_label(self._classify_report_type(end_date)),
                "analysis": analysis,
                "statements": statements,
            }
        except Exception as e:
            logger.error(f"Error getting report detail for {ts_code}/{end_date}: {e}")
            return {"status": "error", "error": str(e)}

    def _get_a_statements(self, ts_code: str, end_date: str) -> Dict[str, Any]:
        """Get A-share three statements for a specific period."""
        try:
            income = self.financial_service.get_income_statement(ts_code, periods=4)
            balance = self.financial_service.get_balance_sheet(ts_code, periods=4)
            cashflow = self.financial_service.get_cash_flow(ts_code, periods=4)
            return {
                "income": income.get("data", []) if income.get("status") == "success" else [],
                "balance": balance.get("data", []) if balance.get("status") == "success" else [],
                "cashflow": cashflow.get("data", []) if cashflow.get("status") == "success" else [],
            }
        except Exception as e:
            logger.error(f"Error getting A-share statements: {e}")
            return {"income": [], "balance": [], "cashflow": []}

    def _get_hk_statements(self, ts_code: str, end_date: str) -> Dict[str, Any]:
        """Get HK three statements for a specific period."""
        try:
            result = self.hk_financial_service.get_full_statements_pivot(ts_code, periods=4)
            if result.get("status") == "success":
                return {
                    "income": result.get("income", []),
                    "balance": result.get("balance", []),
                    "cashflow": result.get("cashflow", []),
                }
            return {"income": [], "balance": [], "cashflow": []}
        except Exception as e:
            logger.error(f"Error getting HK statements: {e}")
            return {"income": [], "balance": [], "cashflow": []}

    # ========== AI Analysis CRUD ==========

    def run_analysis(
        self,
        ts_code: str,
        end_date: str,
        market: str = "A",
        analysis_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """Run professional AI financial analysis and persist the result.

        The analysis follows a professional 8-module methodology:
        1. 盈利能力分析 (Profitability)
        2. 偿债能力分析 (Solvency)
        3. 营运能力分析 (Operational efficiency)
        4. 成长能力分析 (Growth)
        5. 现金流分析 (Cash flow quality)
        6. 杜邦分析 (DuPont decomposition)
        7. 同业对比 (Peer comparison)
        8. 综合投资建议 (Investment recommendation)

        Args:
            ts_code: Stock code
            end_date: Report period
            market: 'A' or 'HK'
            analysis_type: Type of analysis

        Returns:
            The saved analysis record
        """
        try:
            # 1. Gather all financial data first
            company_info = self._get_company_info(ts_code, market)
            stock_name = company_info.get("name", ts_code)

            if market == "HK":
                analysis_data = self.hk_financial_service.get_comprehensive_analysis(ts_code, 8)
            else:
                analysis_data = self.financial_service.get_comprehensive_analysis(ts_code, 8)

            health_score = 0
            if analysis_data.get("status") == "success":
                health_score = analysis_data.get("health_analysis", {}).get("health_score", 0)

            # 2. Build comprehensive professional report using existing Agent + enhanced structuring
            report_content = self._build_professional_report(
                ts_code, stock_name, end_date, market, analysis_data
            )

            # 3. Build data snapshot for persistence
            data_snapshot = self._build_data_snapshot(analysis_data)

            # 4. Extract structured sections
            analysis_sections = self._extract_sections(report_content)

            # 5. Persist to database
            record_id = str(uuid.uuid4())
            report_type = self._classify_report_type(end_date)

            self.db.execute(
                """
                INSERT INTO report_analysis_records 
                (id, ts_code, stock_name, market, end_date, report_type, analysis_type,
                 report_content, data_snapshot, health_score, analysis_sections, analysis_metadata)
                VALUES (%(id)s, %(ts_code)s, %(stock_name)s, %(market)s, %(end_date)s, 
                        %(report_type)s, %(analysis_type)s, %(report_content)s, %(data_snapshot)s,
                        %(health_score)s, %(analysis_sections)s, %(analysis_metadata)s)
                """,
                {
                    "id": record_id,
                    "ts_code": ts_code,
                    "stock_name": stock_name,
                    "market": market,
                    "end_date": end_date,
                    "report_type": report_type,
                    "analysis_type": analysis_type,
                    "report_content": report_content,
                    "data_snapshot": json.dumps(data_snapshot, ensure_ascii=False, default=str),
                    "health_score": float(health_score),
                    "analysis_sections": json.dumps(analysis_sections, ensure_ascii=False),
                    "analysis_metadata": json.dumps({
                        "model": "report_agent",
                        "version": "2.0",
                        "methodology": "professional_8_module",
                        "created_at": datetime.now().isoformat(),
                    }),
                },
            )

            return {
                "status": "success",
                "record": {
                    "id": record_id,
                    "ts_code": ts_code,
                    "stock_name": stock_name,
                    "market": market,
                    "end_date": end_date,
                    "report_type": report_type,
                    "analysis_type": analysis_type,
                    "report_content": report_content,
                    "health_score": health_score,
                    "analysis_sections": analysis_sections,
                    "created_at": datetime.now().isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"Error running analysis for {ts_code}/{end_date}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ========== LLM AI Deep Analysis ==========

    def run_llm_analysis(
        self,
        ts_code: str,
        end_date: str,
        market: str = "A",
    ) -> Dict[str, Any]:
        """Run real LLM-powered deep financial analysis (manually triggered).

        This method calls the configured LLM (e.g., GPT-4 / Kimi) to generate
        professional-grade financial insights based on structured data.

        Args:
            ts_code: Stock code
            end_date: Report period
            market: 'A' or 'HK'

        Returns:
            The saved analysis record with LLM-generated content
        """
        try:
            # 1. Gather financial data
            company_info = self._get_company_info(ts_code, market)
            stock_name = company_info.get("name", ts_code)

            if market == "HK":
                analysis_data = self.hk_financial_service.get_comprehensive_analysis(ts_code, 8)
            else:
                analysis_data = self.financial_service.get_comprehensive_analysis(ts_code, 8)

            health_score = 0
            if analysis_data.get("status") == "success":
                health_score = analysis_data.get("health_analysis", {}).get("health_score", 0)

            # 2. Build prompt for LLM
            prompt = self._build_llm_prompt(ts_code, stock_name, end_date, market, analysis_data)

            # 3. Call LLM
            from stock_datasource.llm.client import get_llm_client

            llm_client = get_llm_client()
            logger.info(f"Starting LLM analysis for {ts_code}/{end_date}, client type: {type(llm_client).__name__}")

            # Run async LLM call in sync context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            system_prompt = (
                "你是一位资深的证券分析师和财务专家，拥有CFA和CPA双证。"
                "请基于提供的财务数据，撰写一份专业、深入、有洞察力的财务分析报告。"
                "要求：\n"
                "1. 用数据说话，每个结论都要有具体数字支撑\n"
                "2. 发现数据背后的深层逻辑和潜在风险\n"
                "3. 对比行业常见水平给出评价\n"
                "4. 提供有实际参考价值的投资建议\n"
                "5. 使用Markdown格式，结构清晰\n"
                "6. 避免空洞的套话，每一句都要有信息量\n"
                "7. 如果数据不足以支撑某个判断，坦诚说明"
            )

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    llm_content = pool.submit(
                        lambda: asyncio.run(
                            llm_client.generate(
                                prompt=prompt,
                                system_prompt=system_prompt,
                                temperature=0.3,
                                max_tokens=4000,
                            )
                        )
                    ).result(timeout=120)
            else:
                llm_content = asyncio.run(
                    llm_client.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=4000,
                    )
                )

            if not llm_content or len(llm_content) < 50:
                return {"status": "error", "error": "LLM returned empty or too short response"}

            # 4. Compose final report: data header + LLM content
            report_type_label = self._report_type_label(self._classify_report_type(end_date))
            year = end_date[:4] if len(end_date) >= 4 else end_date

            report_content = (
                f"# {stock_name}（{ts_code}）{year}年{report_type_label} AI深度分析\n\n"
                f"> 🤖 本报告由AI大模型生成 | 分析日期：{datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"| 报告期：{end_date} | 健康度评分：**{health_score}/100**\n\n"
                f"---\n\n"
                f"{llm_content}\n\n"
                f"---\n\n"
                f"*声明：本分析由AI大模型基于公开财务数据生成，仅供参考，不构成投资建议。"
                f"投资有风险，入市需谨慎。*\n"
            )

            # 5. Persist
            record_id = str(uuid.uuid4())
            report_type = self._classify_report_type(end_date)
            data_snapshot = self._build_data_snapshot(analysis_data)
            analysis_sections = self._extract_sections(report_content)

            self.db.execute(
                """
                INSERT INTO report_analysis_records 
                (id, ts_code, stock_name, market, end_date, report_type, analysis_type,
                 report_content, data_snapshot, health_score, analysis_sections, analysis_metadata)
                VALUES (%(id)s, %(ts_code)s, %(stock_name)s, %(market)s, %(end_date)s, 
                        %(report_type)s, %(analysis_type)s, %(report_content)s, %(data_snapshot)s,
                        %(health_score)s, %(analysis_sections)s, %(analysis_metadata)s)
                """,
                {
                    "id": record_id,
                    "ts_code": ts_code,
                    "stock_name": stock_name,
                    "market": market,
                    "end_date": end_date,
                    "report_type": report_type,
                    "analysis_type": "ai_deep",
                    "report_content": report_content,
                    "data_snapshot": json.dumps(data_snapshot, ensure_ascii=False, default=str),
                    "health_score": float(health_score),
                    "analysis_sections": json.dumps(analysis_sections, ensure_ascii=False),
                    "analysis_metadata": json.dumps({
                        "model": self._get_llm_model_name(),
                        "version": "1.0",
                        "methodology": "llm_deep_analysis",
                        "created_at": datetime.now().isoformat(),
                    }),
                },
            )

            logger.info(f"LLM analysis completed for {ts_code}/{end_date}, id={record_id}")

            return {
                "status": "success",
                "record": {
                    "id": record_id,
                    "ts_code": ts_code,
                    "stock_name": stock_name,
                    "market": market,
                    "end_date": end_date,
                    "report_type": report_type,
                    "analysis_type": "ai_deep",
                    "report_content": report_content,
                    "health_score": health_score,
                    "analysis_sections": analysis_sections,
                    "created_at": datetime.now().isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"Error running LLM analysis for {ts_code}/{end_date}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _build_llm_prompt(
        self,
        ts_code: str,
        stock_name: str,
        end_date: str,
        market: str,
        analysis_data: Dict[str, Any],
    ) -> str:
        """Build a structured prompt for LLM financial analysis."""
        report_type_label = self._report_type_label(self._classify_report_type(end_date))
        year = end_date[:4] if len(end_date) >= 4 else end_date

        summary = analysis_data.get("summary", {})
        health = analysis_data.get("health_analysis", {})
        growth = analysis_data.get("growth_analysis", {})
        profitability = summary.get("profitability", {})
        solvency = summary.get("solvency", {})
        efficiency = summary.get("efficiency", {})
        growth_data = summary.get("growth", {})

        # Format data section
        data_lines = []
        data_lines.append(f"公司：{stock_name}（{ts_code}）")
        data_lines.append(f"市场：{'A股' if market == 'A' else '港股'}")
        data_lines.append(f"报告期：{year}年{report_type_label}（{end_date}）")
        data_lines.append("")
        data_lines.append("## 盈利能力指标")
        for k, label in [("roe", "ROE"), ("roa", "ROA"), ("gross_profit_margin", "毛利率"), ("net_profit_margin", "净利率")]:
            val = profitability.get(k)
            if val is not None and val != "\\N":
                data_lines.append(f"- {label}: {self._fmt_pct(val)}")

        data_lines.append("")
        data_lines.append("## 偿债能力指标")
        for k, label in [("debt_to_assets", "资产负债率"), ("current_ratio", "流动比率"), ("quick_ratio", "速动比率")]:
            val = solvency.get(k)
            if val is not None and val != "\\N":
                data_lines.append(f"- {label}: {self._fmt_num(val) if k != 'debt_to_assets' else self._fmt_pct(val)}")

        data_lines.append("")
        data_lines.append("## 营运能力指标")
        for k, label in [("asset_turnover", "资产周转率"), ("inventory_turnover", "存货周转率"), ("receivable_turnover", "应收账款周转率")]:
            val = efficiency.get(k)
            if val is not None and val != "\\N":
                data_lines.append(f"- {label}: {self._fmt_num(val)}")

        data_lines.append("")
        data_lines.append("## 成长能力指标")
        for k, label in [("revenue_growth", "营收增长率"), ("profit_growth", "净利润增长率")]:
            val = growth_data.get(k)
            if val is not None and val != "\\N":
                data_lines.append(f"- {label}: {self._fmt_pct(val)}")

        data_lines.append("")
        data_lines.append(f"## 财务健康度评分: {health.get('health_score', 0)}/100")

        strengths = health.get("strengths", [])
        weaknesses = health.get("weaknesses", [])
        if strengths:
            data_lines.append("优势: " + "; ".join(strengths))
        if weaknesses:
            data_lines.append("风险: " + "; ".join(weaknesses))

        # Add trend data if available
        trend_data = growth.get("trend_data", [])
        if trend_data:
            data_lines.append("")
            data_lines.append("## 历史趋势数据（近几期）")
            for t in trend_data[-6:]:
                period = t.get("period", "")
                rev = t.get("revenue")
                profit = t.get("net_profit")
                roe = t.get("roe")
                items = [f"期间: {period}"]
                if rev is not None:
                    items.append(f"营收: {rev:.2f}")
                if profit is not None:
                    items.append(f"净利润: {profit:.2f}")
                if roe is not None:
                    items.append(f"ROE: {roe:.2f}%")
                data_lines.append("- " + " | ".join(items))

        data_section = "\n".join(data_lines)

        prompt = f"""请基于以下{stock_name}的财务数据，撰写一份专业深度分析报告。

{data_section}

请按照以下结构输出分析报告：

## 一、核心财务亮点与风险提示
（最重要的3-5个发现，直接点出关键数字和结论）

## 二、盈利能力深度分析
（ROE拆解、利润率变化趋势、与行业对标）

## 三、财务安全性评估
（偿债能力、流动性风险、资本结构合理性）

## 四、经营效率与成长性分析
（营运效率趋势、成长可持续性判断）

## 五、现金流质量评估
（经营现金流与利润匹配度、自由现金流评估）

## 六、投资价值综合评判
（基于以上分析给出明确的投资建议，包含估值参考和风险等级）

注意：每个观点必须用具体数据支撑，避免泛泛而谈。如果某些数据缺失无法判断，请坦诚说明。"""

        return prompt

    @staticmethod
    def _get_llm_model_name() -> str:
        """Get the configured LLM model name."""
        import os
        return os.getenv("OPENAI_MODEL", "unknown")

    def _build_professional_report(
        self,
        ts_code: str,
        stock_name: str,
        end_date: str,
        market: str,
        analysis_data: Dict[str, Any],
    ) -> str:
        """Build a professional 8-module financial analysis report.

        Combines data-driven structured analysis with AI-generated insights.
        """
        report_type_label = self._report_type_label(self._classify_report_type(end_date))
        year = end_date[:4] if len(end_date) >= 4 else end_date

        # Extract data sections
        summary = analysis_data.get("summary", {})
        health = analysis_data.get("health_analysis", {})
        growth = analysis_data.get("growth_analysis", {})
        profitability = summary.get("profitability", {})
        solvency = summary.get("solvency", {})
        efficiency = summary.get("efficiency", {})
        growth_data = summary.get("growth", {})

        health_score = health.get("health_score", 0)
        strengths = health.get("strengths", [])
        weaknesses = health.get("weaknesses", [])
        recommendations = health.get("recommendations", [])

        # Build the report following professional methodology
        report = f"""# {stock_name}（{ts_code}）{year}年{report_type_label}专业财务分析

> 分析日期：{datetime.now().strftime('%Y-%m-%d')} | 报告期：{end_date} | 综合评分：**{health_score}/100**

---

## 一、盈利能力分析 📈

盈利能力是衡量企业获取利润能力的核心指标，反映了企业的经营效率和竞争优势。

| 指标 | 数值 | 评价 |
|------|------|------|
| ROE（净资产收益率） | {self._fmt_pct(profitability.get('roe'))} | {self._rate_indicator(profitability.get('roe'), 'roe')} |
| ROA（总资产收益率） | {self._fmt_pct(profitability.get('roa'))} | {self._rate_indicator(profitability.get('roa'), 'roa')} |
| 毛利率 | {self._fmt_pct(profitability.get('gross_profit_margin'))} | {self._rate_indicator(profitability.get('gross_profit_margin'), 'gross_margin')} |
| 净利率 | {self._fmt_pct(profitability.get('net_profit_margin'))} | {self._rate_indicator(profitability.get('net_profit_margin'), 'net_margin')} |

**分析要点：**
{self._profitability_commentary(profitability)}

---

## 二、偿债能力分析 🛡️

偿债能力反映企业偿还到期债务的能力，是评估财务风险的关键维度。

| 指标 | 数值 | 评价 |
|------|------|------|
| 资产负债率 | {self._fmt_pct(solvency.get('debt_to_assets'))} | {self._rate_indicator(solvency.get('debt_to_assets'), 'debt_ratio')} |
| 流动比率 | {self._fmt_num(solvency.get('current_ratio'))} | {self._rate_indicator(solvency.get('current_ratio'), 'current_ratio')} |
| 速动比率 | {self._fmt_num(solvency.get('quick_ratio'))} | {self._rate_indicator(solvency.get('quick_ratio'), 'quick_ratio')} |

**分析要点：**
{self._solvency_commentary(solvency)}

---

## 三、营运能力分析 ⚙️

营运能力体现企业资产运转效率，是评估管理层经营水平的重要依据。

| 指标 | 数值 | 评价 |
|------|------|------|
| 资产周转率 | {self._fmt_num(efficiency.get('asset_turnover'))} | {self._rate_indicator(efficiency.get('asset_turnover'), 'asset_turnover')} |
| 存货周转率 | {self._fmt_num(efficiency.get('inventory_turnover'))} | {self._rate_indicator(efficiency.get('inventory_turnover'), 'inventory_turnover')} |
| 应收账款周转率 | {self._fmt_num(efficiency.get('receivable_turnover'))} | {self._rate_indicator(efficiency.get('receivable_turnover'), 'receivable_turnover')} |

**分析要点：**
{self._efficiency_commentary(efficiency)}

---

## 四、成长能力分析 🚀

成长能力反映企业未来发展潜力和扩张速度。

| 指标 | 数值 | 评价 |
|------|------|------|
| 营收增长率 | {self._fmt_pct(growth_data.get('revenue_growth'))} | {self._rate_growth(growth_data.get('revenue_growth'))} |
| 净利润增长率 | {self._fmt_pct(growth_data.get('profit_growth'))} | {self._rate_growth(growth_data.get('profit_growth'))} |

**分析要点：**
{self._growth_commentary(growth_data)}

---

## 五、现金流分析 💰

现金流是企业的"血液"，健康的现金流是企业持续经营的基础。

**分析要点：**
{self._cashflow_commentary(analysis_data)}

---

## 六、杜邦分析 🔍

杜邦分析将ROE分解为三个核心驱动因素，揭示盈利能力的深层结构。

**ROE = 净利率 × 资产周转率 × 权益乘数**

| 驱动因素 | 数值 | 说明 |
|----------|------|------|
| 净利率 | {self._fmt_pct(profitability.get('net_profit_margin'))} | 每元营收贡献的利润 |
| 资产周转率 | {self._fmt_num(efficiency.get('asset_turnover'))} | 资产运用效率 |
| 权益乘数 | {self._fmt_num(self._calc_equity_multiplier(solvency))} | 财务杠杆水平 |
| **ROE** | **{self._fmt_pct(profitability.get('roe'))}** | **综合盈利能力** |

{self._dupont_commentary(profitability, efficiency, solvency)}

---

## 七、综合评价与风险提示 ⚠️

### 财务健康度评分：{health_score}/100 {self._score_emoji(health_score)}

### 主要优势
{self._format_bullet_list(strengths, '暂无明显优势')}

### 关注风险
{self._format_bullet_list(weaknesses, '财务状况良好，无明显风险点')}

---

## 八、投资建议 💡

{self._format_bullet_list(recommendations, '建议投资者结合行业前景和估值水平综合判断')}

---

*声明：本分析基于公开财务数据自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
"""
        # Additionally try to get AI Agent generated insights and append if available
        try:
            if market == "HK":
                from stock_datasource.agents.hk_report_agent import (
                    get_hk_comprehensive_financial_analysis,
                )
                ai_content = get_hk_comprehensive_financial_analysis(ts_code, periods=8)
                if isinstance(ai_content, dict):
                    ai_content = ai_content.get("report", "")
            else:
                from stock_datasource.agents.report_agent import (
                    get_comprehensive_financial_analysis,
                )
                ai_result = get_comprehensive_financial_analysis(ts_code, periods=8)
                if isinstance(ai_result, dict):
                    ai_content = ai_result.get("report", "")
                else:
                    ai_content = str(ai_result)

            if ai_content and len(ai_content) > 50:
                report += f"\n\n---\n\n## 附录：AI深度洞察\n\n{ai_content}\n"
        except Exception as e:
            logger.warning(f"AI agent insights generation skipped: {e}")

        return report

    # ========== Report Generation Helpers ==========

    @staticmethod
    def _fmt_pct(val, fallback: str = "N/A") -> str:
        """Format a percentage value."""
        if val is None or val == "\\N" or val == "None" or val == "":
            return fallback
        try:
            return f"{float(val):.2f}%"
        except (ValueError, TypeError):
            return fallback

    @staticmethod
    def _fmt_num(val, fallback: str = "N/A") -> str:
        """Format a numeric value."""
        if val is None or val == "\\N" or val == "None" or val == "":
            return fallback
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return fallback

    @staticmethod
    def _rate_indicator(val, indicator_type: str) -> str:
        """Rate an indicator value with emoji."""
        if val is None or val == "\\N" or val == "":
            return "⬜ 数据缺失"
        try:
            v = float(val)
        except (ValueError, TypeError):
            return "⬜ 数据缺失"

        thresholds = {
            "roe": [(15, "🟢 优秀"), (8, "🟡 良好"), (0, "🟠 一般"), (float("-inf"), "🔴 较弱")],
            "roa": [(8, "🟢 优秀"), (4, "🟡 良好"), (0, "🟠 一般"), (float("-inf"), "🔴 较弱")],
            "gross_margin": [(40, "🟢 优秀"), (20, "🟡 良好"), (10, "🟠 一般"), (float("-inf"), "🔴 较弱")],
            "net_margin": [(15, "🟢 优秀"), (8, "🟡 良好"), (0, "🟠 一般"), (float("-inf"), "🔴 较弱")],
            "debt_ratio": [(40, "🟢 稳健"), (60, "🟡 适中"), (70, "🟠 偏高"), (float("inf"), "🔴 高风险")],
            "current_ratio": [(2, "🟢 充裕"), (1.5, "🟡 适中"), (1, "🟠 偏紧"), (float("-inf"), "🔴 紧张")],
            "quick_ratio": [(1.5, "🟢 充裕"), (1, "🟡 适中"), (0.5, "🟠 偏紧"), (float("-inf"), "🔴 紧张")],
            "asset_turnover": [(1, "🟢 高效"), (0.5, "🟡 适中"), (float("-inf"), "🟠 偏低")],
            "inventory_turnover": [(8, "🟢 高效"), (4, "🟡 适中"), (float("-inf"), "🟠 偏低")],
            "receivable_turnover": [(10, "🟢 高效"), (5, "🟡 适中"), (float("-inf"), "🟠 偏低")],
        }

        rules = thresholds.get(indicator_type, [])
        if indicator_type == "debt_ratio":
            # Lower is better for debt
            for threshold, label in rules:
                if v <= threshold:
                    return label
            return "🔴 高风险"
        else:
            for threshold, label in rules:
                if v >= threshold:
                    return label
            return "🟠 一般"

    @staticmethod
    def _rate_growth(val) -> str:
        """Rate growth value."""
        if val is None or val == "\\N" or val == "":
            return "⬜ 数据缺失"
        try:
            v = float(val)
        except (ValueError, TypeError):
            return "⬜ 数据缺失"
        if v >= 30:
            return "🟢 高速增长"
        elif v >= 10:
            return "🟡 稳健增长"
        elif v >= 0:
            return "🟠 低速增长"
        elif v >= -10:
            return "🟠 小幅下滑"
        else:
            return "🔴 显著下降"

    @staticmethod
    def _score_emoji(score: float) -> str:
        """Get emoji for health score."""
        if score >= 80:
            return "🌟"
        elif score >= 60:
            return "✅"
        elif score >= 40:
            return "⚠️"
        else:
            return "🔴"

    @staticmethod
    def _calc_equity_multiplier(solvency: dict) -> Optional[float]:
        """Calculate equity multiplier from debt-to-assets ratio."""
        debt_ratio = solvency.get("debt_to_assets")
        if debt_ratio is None or debt_ratio == "\\N":
            return None
        try:
            d = float(debt_ratio) / 100
            if d >= 1:
                return None
            return 1 / (1 - d)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def _format_bullet_list(items: List[str], empty_msg: str = "") -> str:
        """Format a list of strings as markdown bullets."""
        if not items:
            return f"- {empty_msg}" if empty_msg else ""
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _profitability_commentary(prof: dict) -> str:
        """Generate profitability commentary."""
        parts = []
        roe = prof.get("roe")
        gross = prof.get("gross_profit_margin")
        net = prof.get("net_profit_margin")

        if roe is not None and roe != "\\N":
            try:
                roe_val = float(roe)
                if roe_val >= 15:
                    parts.append(f"- ROE达{roe_val:.2f}%，表明公司股东权益回报率优秀，核心盈利能力突出")
                elif roe_val >= 8:
                    parts.append(f"- ROE为{roe_val:.2f}%，股东权益回报处于良好水平")
                else:
                    parts.append(f"- ROE仅为{roe_val:.2f}%，盈利能力有待提升")
            except (ValueError, TypeError):
                pass

        if gross is not None and gross != "\\N":
            try:
                gross_val = float(gross)
                if gross_val >= 40:
                    parts.append(f"- 毛利率{gross_val:.2f}%，反映出较强的产品定价权和竞争壁垒")
                elif gross_val >= 20:
                    parts.append(f"- 毛利率{gross_val:.2f}%，处于行业中等水平")
                else:
                    parts.append(f"- 毛利率仅{gross_val:.2f}%，产品附加值较低，需关注成本控制")
            except (ValueError, TypeError):
                pass

        return "\n".join(parts) if parts else "- 盈利数据不足，建议结合行业特征综合判断"

    @staticmethod
    def _solvency_commentary(solv: dict) -> str:
        """Generate solvency commentary."""
        parts = []
        debt = solv.get("debt_to_assets")
        current = solv.get("current_ratio")

        if debt is not None and debt != "\\N":
            try:
                debt_val = float(debt)
                if debt_val <= 40:
                    parts.append(f"- 资产负债率{debt_val:.2f}%，财务结构稳健，偿债压力小")
                elif debt_val <= 60:
                    parts.append(f"- 资产负债率{debt_val:.2f}%，财务杠杆适中")
                else:
                    parts.append(f"- 资产负债率高达{debt_val:.2f}%，需关注债务风险")
            except (ValueError, TypeError):
                pass

        if current is not None and current != "\\N":
            try:
                current_val = float(current)
                if current_val >= 2:
                    parts.append(f"- 流动比率{current_val:.2f}，短期偿债能力充裕")
                elif current_val >= 1:
                    parts.append(f"- 流动比率{current_val:.2f}，短期偿债能力基本满足")
                else:
                    parts.append(f"- 流动比率仅{current_val:.2f}，短期流动性风险较高")
            except (ValueError, TypeError):
                pass

        return "\n".join(parts) if parts else "- 偿债能力数据不足，建议关注债务到期结构"

    @staticmethod
    def _efficiency_commentary(eff: dict) -> str:
        """Generate operational efficiency commentary."""
        parts = []
        at = eff.get("asset_turnover")

        if at is not None and at != "\\N":
            try:
                at_val = float(at)
                if at_val >= 1:
                    parts.append(f"- 资产周转率{at_val:.2f}，资产运用效率较高")
                elif at_val >= 0.5:
                    parts.append(f"- 资产周转率{at_val:.2f}，处于正常水平")
                else:
                    parts.append(f"- 资产周转率仅{at_val:.2f}，资产运用效率偏低，可能存在资产冗余")
            except (ValueError, TypeError):
                pass

        return "\n".join(parts) if parts else "- 营运效率数据不足，建议参考行业平均水平"

    @staticmethod
    def _growth_commentary(growth: dict) -> str:
        """Generate growth commentary."""
        parts = []
        rev_g = growth.get("revenue_growth")
        prof_g = growth.get("profit_growth")

        if rev_g is not None and rev_g != "\\N":
            try:
                rev_val = float(rev_g)
                if rev_val >= 20:
                    parts.append(f"- 营收增长{rev_val:.2f}%，展现出强劲的业务扩张势头")
                elif rev_val >= 0:
                    parts.append(f"- 营收增长{rev_val:.2f}%，保持正向增长")
                else:
                    parts.append(f"- 营收下降{abs(rev_val):.2f}%，业务面临收缩压力")
            except (ValueError, TypeError):
                pass

        if prof_g is not None and prof_g != "\\N":
            try:
                prof_val = float(prof_g)
                if rev_g is not None:
                    try:
                        rev_val = float(rev_g)
                        if prof_val > rev_val:
                            parts.append("- 利润增速高于营收增速，盈利质量有所提升")
                        elif prof_val < rev_val and prof_val >= 0:
                            parts.append("- 利润增速低于营收增速，需关注成本费用控制")
                    except (ValueError, TypeError):
                        pass
            except (ValueError, TypeError):
                pass

        return "\n".join(parts) if parts else "- 成长性数据不足，建议追踪近几期变化趋势"

    @staticmethod
    def _cashflow_commentary(analysis_data: dict) -> str:
        """Generate cash flow commentary."""
        parts = []
        parts.append("- 经营活动现金流是判断企业造血能力的核心指标")
        parts.append("- 理想模型为「经营活动流入 + 投资活动流出 + 筹资活动流出」")
        parts.append("- 需重点关注经营现金流与净利润的匹配程度（现金流/净利润 > 1 为佳）")

        health = analysis_data.get("health_analysis", {})
        recs = health.get("recommendations", [])
        cashflow_recs = [r for r in recs if "现金" in r or "cash" in r.lower()]
        if cashflow_recs:
            parts.append("")
            for rec in cashflow_recs:
                parts.append(f"- {rec}")

        return "\n".join(parts)

    @staticmethod
    def _dupont_commentary(prof: dict, eff: dict, solv: dict) -> str:
        """Generate DuPont analysis commentary."""
        parts = ["**杜邦分析解读：**"]

        net_margin = prof.get("net_profit_margin")
        at = eff.get("asset_turnover")
        debt = solv.get("debt_to_assets")

        drivers = []
        if net_margin is not None and net_margin != "\\N":
            try:
                nm = float(net_margin)
                if nm >= 15:
                    drivers.append("利润率驱动型（高净利率）")
                else:
                    drivers.append("非利润率驱动")
            except (ValueError, TypeError):
                pass

        if at is not None and at != "\\N":
            try:
                at_val = float(at)
                if at_val >= 1:
                    drivers.append("资产周转驱动型（高周转）")
            except (ValueError, TypeError):
                pass

        if debt is not None and debt != "\\N":
            try:
                d = float(debt)
                if d >= 60:
                    drivers.append("杠杆驱动型（高负债率）")
            except (ValueError, TypeError):
                pass

        if drivers:
            parts.append(f"- 公司ROE驱动模式为：{'、'.join(drivers)}")
        else:
            parts.append("- 数据不足以判断ROE核心驱动因素")

        return "\n".join(parts)

    def get_analysis_history(
        self, ts_code: str, end_date: Optional[str] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """Get historical analysis records for a company.

        Args:
            ts_code: Stock code
            end_date: Optional filter by report period
            limit: Max records to return
        """
        try:
            where_clauses = ["ts_code = %(ts_code)s"]
            params: Dict[str, Any] = {"ts_code": ts_code, "limit": limit}

            if end_date:
                where_clauses.append("end_date = %(end_date)s")
                params["end_date"] = end_date

            where_sql = " AND ".join(where_clauses)

            query = f"""
                SELECT id, ts_code, stock_name, market, end_date, report_type,
                       analysis_type, report_content, health_score, analysis_sections,
                       analysis_metadata, created_at
                FROM report_analysis_records FINAL
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %(limit)s
            """
            rows = self.db.execute(query, params)

            records = []
            for row in rows:
                records.append({
                    "id": row[0],
                    "ts_code": row[1],
                    "stock_name": row[2],
                    "market": row[3],
                    "end_date": row[4],
                    "report_type": row[5],
                    "analysis_type": row[6],
                    "report_content": row[7],
                    "health_score": row[8],
                    "analysis_sections": self._safe_json_parse(row[9]),
                    "analysis_metadata": self._safe_json_parse(row[10]),
                    "created_at": row[11].isoformat() if hasattr(row[11], "isoformat") else str(row[11]),
                })

            return {"status": "success", "records": records}
        except Exception as e:
            logger.error(f"Error getting analysis history for {ts_code}: {e}")
            return {"status": "error", "error": str(e), "records": []}

    def get_analysis_record(self, record_id: str) -> Dict[str, Any]:
        """Get a single analysis record by ID."""
        try:
            query = """
                SELECT id, ts_code, stock_name, market, end_date, report_type,
                       analysis_type, report_content, data_snapshot, health_score,
                       analysis_sections, analysis_metadata, created_at
                FROM report_analysis_records FINAL
                WHERE id = %(id)s
                LIMIT 1
            """
            rows = self.db.execute(query, {"id": record_id})

            if not rows:
                return {"status": "error", "error": "Analysis record not found"}

            row = rows[0]
            return {
                "status": "success",
                "record": {
                    "id": row[0],
                    "ts_code": row[1],
                    "stock_name": row[2],
                    "market": row[3],
                    "end_date": row[4],
                    "report_type": row[5],
                    "analysis_type": row[6],
                    "report_content": row[7],
                    "data_snapshot": self._safe_json_parse(row[8]),
                    "health_score": row[9],
                    "analysis_sections": self._safe_json_parse(row[10]),
                    "analysis_metadata": self._safe_json_parse(row[11]),
                    "created_at": row[12].isoformat() if hasattr(row[12], "isoformat") else str(row[12]),
                },
            }
        except Exception as e:
            logger.error(f"Error getting analysis record {record_id}: {e}")
            return {"status": "error", "error": str(e)}

    # ========== Helpers ==========

    def _get_company_info(self, ts_code: str, market: str = "A") -> Dict[str, Any]:
        """Get company basic info."""
        try:
            if market == "HK":
                return {
                    "ts_code": ts_code,
                    "symbol": ts_code.replace(".HK", ""),
                    "name": ts_code,
                    "area": "",
                    "industry": "",
                    "market": "HK",
                    "list_date": "",
                }

            query = """
                SELECT ts_code, symbol, name, area, industry, market, list_date
                FROM ods_stock_basic FINAL
                WHERE ts_code = %(ts_code)s
                LIMIT 1
            """
            rows = self.db.execute(query, {"ts_code": ts_code})
            if rows:
                row = rows[0]
                list_date_val = row[6]
                if hasattr(list_date_val, "strftime"):
                    list_date_val = list_date_val.strftime("%Y-%m-%d")
                return {
                    "ts_code": row[0],
                    "symbol": row[1],
                    "name": row[2],
                    "area": row[3] or "",
                    "industry": row[4] or "",
                    "market": row[5] or "",
                    "list_date": str(list_date_val) if list_date_val else "",
                }
            return {"ts_code": ts_code, "name": ts_code, "symbol": "", "area": "", "industry": "", "market": "A", "list_date": ""}
        except Exception as e:
            logger.error(f"Error getting company info for {ts_code}: {e}")
            return {"ts_code": ts_code, "name": ts_code, "symbol": "", "area": "", "industry": "", "market": market, "list_date": ""}

    def _get_analysis_status_map(self, ts_code: str) -> Dict[str, bool]:
        """Get a map of end_date -> has_analysis for a stock."""
        try:
            query = """
                SELECT DISTINCT end_date
                FROM report_analysis_records FINAL
                WHERE ts_code = %(ts_code)s
            """
            rows = self.db.execute(query, {"ts_code": ts_code})
            return {str(row[0]): True for row in rows}
        except Exception:
            return {}

    def _build_data_snapshot(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a compact data snapshot for persistence."""
        if analysis_data.get("status") != "success":
            return {}
        snapshot = {}
        for key in ["summary", "health_analysis", "growth_analysis"]:
            if key in analysis_data:
                snapshot[key] = analysis_data[key]
        return snapshot

    def _extract_sections(self, report_content: str) -> List[Dict[str, str]]:
        """Extract structured sections from markdown report."""
        import re

        sections = []
        # Split by ## or ### headers
        parts = re.split(r'\n(#{2,3}\s+)', report_content)

        current_title = ""
        for i, part in enumerate(parts):
            if re.match(r'^#{2,3}\s+', part):
                current_title = part.strip("# \n")
            elif current_title:
                sections.append({
                    "title": current_title,
                    "content": part.strip(),
                })
                current_title = ""

        return sections

    @staticmethod
    def _classify_report_type(end_date: str) -> str:
        """Classify report type by end_date string."""
        date_str = str(end_date).replace("-", "")
        if len(date_str) >= 8:
            month_day = date_str[4:8]
            if month_day == "1231":
                return "annual"
            elif month_day == "0630":
                return "semi_annual"
            elif month_day == "0331":
                return "q1"
            elif month_day == "0930":
                return "q3"
        return "other"

    @staticmethod
    def _report_type_label(report_type: str) -> str:
        """Get human-readable label for report type."""
        labels = {
            "annual": "年报",
            "semi_annual": "中报",
            "q1": "一季报",
            "q3": "三季报",
            "other": "其他",
        }
        return labels.get(report_type, "其他")

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        """Safely convert value to float."""
        if val is None or val == "\\N" or val == "None" or val == "":
            return None
        try:
            f = float(val)
            if f != f:  # NaN check
                return None
            return f
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_json_parse(val) -> Any:
        """Safely parse JSON string."""
        if not val:
            return {}
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
