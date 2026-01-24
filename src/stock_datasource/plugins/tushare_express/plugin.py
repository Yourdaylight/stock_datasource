"""Tushare 业绩快报插件"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareExpressPlugin(BasePlugin):
    """业绩快报数据插件"""

    @property
    def name(self) -> str:
        return "tushare_express"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Tushare 业绩快报数据插件"

    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("rate_limit", 120)

    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_data(self, **kwargs) -> pd.DataFrame:
        """
        提取业绩快报数据

        Args:
            ts_code: 股票代码
            ann_date: 公告日期
            start_date: 公告开始日期
            end_date: 公告结束日期
            period: 报告期
            trade_date: 交易日（用于批量模式）

        Returns:
            业绩快报数据DataFrame
        """
        ts_code = kwargs.get("ts_code")
        ann_date = kwargs.get("ann_date")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period = kwargs.get("period")
        trade_date = kwargs.get("trade_date")

        # Batch mode: extract for all stocks if ts_code not provided
        if not ts_code:
            if not self.db:
                raise ValueError("Database not initialized for batch mode")
            
            self.logger.info("Extracting express data for all stocks (batch mode)")
            
            # Get all stock codes from stock_basic table
            stocks_query = "SELECT DISTINCT ts_code FROM ods_stock_basic WHERE list_status = 'L'"
            stocks_df = self.db.execute_query(stocks_query)
            
            if stocks_df.empty:
                self.logger.warning("No stocks found in stock_basic table")
                return pd.DataFrame()
            
            all_data = []
            for idx, row in stocks_df.iterrows():
                stock_code = row['ts_code']
                try:
                    self.logger.info(f"Extracting express data for {stock_code} ({idx+1}/{len(stocks_df)})")
                    
                    # Use trade_date to set end_date if provided
                    if trade_date:
                        stock_end_date = trade_date.replace('-', '')
                    else:
                        stock_end_date = end_date
                    
                    data = extractor.extract(
                        ts_code=stock_code,
                        ann_date=ann_date,
                        start_date=start_date,
                        end_date=stock_end_date,
                        period=period,
                    )
                    
                    if not data.empty:
                        all_data.append(data)
                    
                    # Rate limiting between API calls
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract express for {stock_code}: {e}")
                    continue
            
            if not all_data:
                self.logger.warning("No express data extracted for any stock")
                return pd.DataFrame()
            
            combined_data = pd.concat(all_data, ignore_index=True)
            # Add system columns for batch mode
            combined_data['version'] = int(datetime.now().timestamp())
            combined_data['_ingested_at'] = datetime.now()
            self.logger.info(f"Extracted {len(combined_data)} express records from {len(all_data)} stocks")
            return combined_data
        
        # Single stock mode
        self.logger.info(f"Extracting express data for ts_code={ts_code}")

        data = extractor.extract(
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
        )

        if data.empty:
            self.logger.warning(f"No express data found for {ts_code}")
            return pd.DataFrame()

        # Add metadata
        data["version"] = int(datetime.now().timestamp())
        data["_ingested_at"] = datetime.now()

        self.logger.info(f"Extracted {len(data)} express records")
        return data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据"""
        if data.empty:
            self.logger.warning("Empty express data")
            return True

        required_columns = ["ts_code", "ann_date", "end_date"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False

        self.logger.info(f"Express data validation passed for {len(data)} records")
        return True

    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """转换数据"""
        if data.empty:
            return data

        data = data.copy()

        # 转换日期格式
        date_columns = ["ann_date", "end_date"]
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format="%Y%m%d", errors="coerce").dt.date

        # 转换数值类型
        numeric_columns = [
            "revenue",
            "operate_profit",
            "total_profit",
            "n_income",
            "total_assets",
            "total_hldr_eqy_exc_min_int",
            "diluted_eps",
            "diluted_roe",
            "yoy_net_profit",
            "bps",
            "yoy_sales",
            "yoy_op",
            "yoy_tp",
            "yoy_dedu_np",
            "yoy_eps",
            "yoy_roe",
            "growth_assets",
            "yoy_equity",
            "growth_bps",
            "or_last_year",
            "op_last_year",
            "tp_last_year",
            "np_last_year",
            "eps_last_year",
            "open_net_assets",
            "open_bps",
        ]
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        self.logger.info(f"Transformed {len(data)} express records")
        return data

    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """加载数据到数据库"""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}

        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}

        results = {
            "status": "success",
            "tables_loaded": [],
            "total_records": 0,
        }

        try:
            table_name = "ods_express"
            self.logger.info(f"Loading {len(data)} records into {table_name}")

            ods_data = data.copy()
            ods_data = self._prepare_data_for_insert(table_name, ods_data)
            self.db.insert_dataframe(table_name, ods_data)

            results["tables_loaded"].append({"table": table_name, "records": len(ods_data)})
            results["total_records"] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results["status"] = "failed"
            results["error"] = str(e)

        return results

    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
