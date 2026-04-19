"""Portfolio service for managing user positions."""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position data model."""

    id: str
    ts_code: str
    stock_name: str
    quantity: int
    cost_price: float
    buy_date: str
    current_price: float | None = None
    market_value: float | None = None
    profit_loss: float | None = None
    profit_rate: float | None = None
    daily_change: float | None = None  # 今日涨跌额
    daily_pct_chg: float | None = None  # 今日涨跌幅(%)
    prev_close: float | None = None  # 昨收价
    notes: str | None = None
    price_update_time: str | None = None


@dataclass
class PortfolioSummary:
    """Portfolio summary data model."""

    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    daily_change: float
    daily_change_rate: float
    position_count: int


class PortfolioService:
    """Portfolio service for managing positions."""

    def __init__(self):
        self._db = None
        # In-memory storage for demo (should be replaced with database)
        self._positions: dict[str, Position] = {}

        # Add some sample data
        sample_position = Position(
            id="pos_001",
            ts_code="600519.SH",
            stock_name="贵州茅台",
            quantity=100,
            cost_price=1700.0,
            buy_date="2024-01-01",
            current_price=1800.0,
            market_value=180000.0,
            profit_loss=10000.0,
            profit_rate=5.88,
            notes="初始持仓",
        )
        self._positions[sample_position.id] = sample_position

    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client

                self._db = db_client
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db

    async def get_positions(
        self, user_id: str = "default_user", profile_id: str | None = None
    ) -> list[Position]:
        """Get all positions for a user, optionally filtered by profile_id."""
        try:
            if self.db is not None:
                # Always filter by user_id for security
                where = "WHERE user_id = %(user_id)s"
                params: dict[str, Any] = {"user_id": user_id}
                if profile_id:
                    where += " AND profile_id = %(profile_id)s"
                    params["profile_id"] = profile_id

                query = f"""
                    SELECT 
                        id, ts_code, stock_name, quantity, cost_price, 
                        buy_date, current_price, market_value, profit_loss, 
                        profit_rate, notes, profile_id
                    FROM user_positions 
                    {where}
                    ORDER BY buy_date DESC
                """
                df = self.db.execute_query(query, params)

                if not df.empty:
                    positions = []
                    ts_codes = df["ts_code"].unique().tolist()

                    # 批量获取所有股票的最新价格
                    prices_cache = await self._batch_get_latest_prices(ts_codes)

                    for _, row in df.iterrows():
                        stock_name = row["stock_name"]
                        # 修正无效的 stock_name（fallback 值等于 ts_code 或以"股票"开头）
                        name_fixed = False
                        if (
                            not stock_name
                            or stock_name == row["ts_code"]
                            or stock_name.startswith("股票")
                        ):
                            stock_name = await self._get_stock_name(row["ts_code"])
                            name_fixed = True

                        position = Position(
                            id=str(row["id"]),
                            ts_code=row["ts_code"],
                            stock_name=stock_name,
                            quantity=int(row["quantity"]),
                            cost_price=float(row["cost_price"]),
                            buy_date=str(row["buy_date"]),
                            current_price=float(row["current_price"])
                            if pd.notna(row["current_price"])
                            else None,
                            market_value=float(row["market_value"])
                            if pd.notna(row["market_value"])
                            else None,
                            profit_loss=float(row["profit_loss"])
                            if pd.notna(row["profit_loss"])
                            else None,
                            profit_rate=float(row["profit_rate"])
                            if pd.notna(row["profit_rate"])
                            else None,
                            notes=row["notes"] if pd.notna(row["notes"]) else None,
                        )
                        # Update current prices and calculations using cached prices
                        await self._update_position_prices(position, prices_cache)
                        # 修正后的名称回写数据库
                        if name_fixed and self.db is not None:
                            try:
                                self.db.execute(
                                    "ALTER TABLE user_positions UPDATE stock_name = %(name)s WHERE id = %(id)s",
                                    {"name": stock_name, "id": position.id},
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to update stock_name in DB for {position.ts_code}: {e}"
                                )
                        positions.append(position)

                    return positions
        except Exception as e:
            logger.warning(f"Failed to get positions from database: {e}")

        # Fallback to in-memory storage
        positions = list(self._positions.values())

        # Update current prices and calculations
        for position in positions:
            await self._update_position_prices(position)

        return positions

    async def add_position(
        self,
        ts_code: str,
        quantity: int,
        cost_price: float,
        buy_date: str,
        notes: str | None = None,
        user_id: str = "default_user",
        profile_id: str | None = None,
    ) -> Position:
        """Add a new position."""
        position_id = str(uuid.uuid4())

        # Get stock name
        stock_name = await self._get_stock_name(ts_code)

        position = Position(
            id=position_id,
            ts_code=ts_code,
            stock_name=stock_name,
            quantity=quantity,
            cost_price=cost_price,
            buy_date=buy_date,
            notes=notes,
        )

        # Update current price and calculations
        await self._update_position_prices(position)

        try:
            if self.db is not None:
                # Try to save to database
                query = """
                    INSERT INTO user_positions 
                    (id, user_id, ts_code, stock_name, quantity, cost_price, buy_date, 
                     current_price, market_value, profit_loss, profit_rate, notes, profile_id)
                    VALUES (%(id)s, %(user_id)s, %(ts_code)s, %(stock_name)s, %(quantity)s, %(cost_price)s, 
                            %(buy_date)s, %(current_price)s, %(market_value)s, 
                            %(profit_loss)s, %(profit_rate)s, %(notes)s, %(profile_id)s)
                """
                params = {
                    "id": position.id,
                    "user_id": user_id,
                    "ts_code": position.ts_code,
                    "stock_name": position.stock_name,
                    "quantity": position.quantity,
                    "cost_price": position.cost_price,
                    "buy_date": position.buy_date,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "profit_loss": position.profit_loss,
                    "profit_rate": position.profit_rate,
                    "notes": position.notes,
                    "profile_id": profile_id or "default",
                }
                self.db.execute(query, params)
                logger.info(
                    f"Position {position_id} saved to database for user {user_id}"
                )
        except Exception as e:
            logger.warning(f"Failed to save position to database: {e}")

        # Always save to in-memory storage as backup
        self._positions[position_id] = position
        logger.info(f"Position {position_id} added: {ts_code}")

        return position

    async def delete_position(
        self, position_id: str, user_id: str = "default_user"
    ) -> bool:
        """Delete a position."""
        try:
            if self.db is not None:
                # Try to delete from database (only if belongs to user)
                query = "DELETE FROM user_positions WHERE id = %(id)s AND user_id = %(user_id)s"
                self.db.execute(query, {"id": position_id, "user_id": user_id})
                logger.info(
                    f"Position {position_id} deleted from database for user {user_id}"
                )
        except Exception as e:
            logger.warning(f"Failed to delete position from database: {e}")

        # Always delete from in-memory storage
        if position_id in self._positions:
            del self._positions[position_id]
            logger.info(f"Position {position_id} deleted")
            return True

        return False

    async def get_summary(self, user_id: str = "default_user") -> PortfolioSummary:
        """Get portfolio summary for a user."""
        positions = await self.get_positions(user_id=user_id)

        if not positions:
            return PortfolioSummary(
                total_value=0.0,
                total_cost=0.0,
                total_profit=0.0,
                profit_rate=0.0,
                daily_change=0.0,
                daily_change_rate=0.0,
                position_count=0,
            )

        total_cost = sum(p.quantity * p.cost_price for p in positions)
        total_value = sum(p.market_value or 0 for p in positions)
        total_profit = total_value - total_cost
        profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0

        # 从各持仓的今日涨跌汇总计算当日盈亏和当日收益率（不再用 mock 值）
        daily_change = sum(
            (p.daily_change or 0) * p.quantity if p.daily_change else 0
            for p in positions
        )
        daily_change_rate = (daily_change / total_value * 100) if total_value > 0 else 0

        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_profit=total_profit,
            profit_rate=profit_rate,
            daily_change=daily_change,
            daily_change_rate=daily_change_rate,
            position_count=len(positions),
        )

    async def _get_stock_name(self, ts_code: str) -> str:
        """Get stock name by code. Supports A-shares, ETFs and HK stocks."""
        if self.db is not None:
            try:
                # 1. A股
                query = (
                    "SELECT name FROM ods_stock_basic WHERE ts_code = %(code)s LIMIT 1"
                )
                df = self.db.execute_query(query, {"code": ts_code})
                if not df.empty:
                    return df.iloc[0]["name"]
            except Exception as e:
                logger.warning(f"Failed to get A-share name for {ts_code}: {e}")

            try:
                # 2. ETF (cname字段)
                query_etf = (
                    "SELECT cname FROM ods_etf_basic WHERE ts_code = %(code)s LIMIT 1"
                )
                df_etf = self.db.execute_query(query_etf, {"code": ts_code})
                if not df_etf.empty:
                    return df_etf.iloc[0]["cname"]
            except Exception as e:
                logger.warning(f"Failed to get ETF name for {ts_code}: {e}")

            try:
                # 3. 港股
                if ts_code.endswith(".HK"):
                    query_hk = (
                        "SELECT name FROM ods_hk_basic WHERE ts_code = %(code)s LIMIT 1"
                    )
                    df_hk = self.db.execute_query(query_hk, {"code": ts_code})
                    if not df_hk.empty:
                        return df_hk.iloc[0]["name"]
            except Exception as e:
                logger.warning(f"Failed to get HK stock name for {ts_code}: {e}")

        # Fallback to mock names
        stock_names = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行",
            "000002.SZ": "万科A",
            "600036.SH": "招商银行",
            "000858.SZ": "五粮液",
        }
        return stock_names.get(ts_code, ts_code)

    @staticmethod
    def _is_market_closed() -> bool:
        """判断当前是否已收盘（A股 15:00 后、港股 16:10 后视为收盘）。"""
        now = datetime.now()
        hhmm = now.hour * 100 + now.minute
        weekday = now.weekday()
        if weekday >= 5:  # 周末
            return True
        # A 股 15:05 后视为收盘
        if hhmm > 1505:
            return True
        return False

    async def _batch_get_latest_prices(
        self, ts_codes: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Batch get latest prices for multiple stocks.

        Returns dict mapping ts_code -> {'close': float, 'trade_time': str, 'prev_close': float|None}

        Priority logic:
          - 盘中: rt_minute_latest (realtime) > on-demand TuShare API > ods_daily (daily close)
          - 收盘后: 如果 rt_minute_latest 的时间 < 15:00 (说明不是收盘价),
                    则 fallback 到日线收盘价(15:00:00), 避免显示盘中过期时间
        """
        prices = {}
        if not ts_codes:
            return prices

        market_closed = self._is_market_closed()

        # 1. 从分钟缓存获取最新价
        try:
            from stock_datasource.modules.realtime_minute.cache_store import (
                get_cache_store,
            )

            cache = get_cache_store()
            if cache.available:
                for code in ts_codes:
                    latest = cache.get_latest("", code, "1min")
                    if latest and latest.get("close") is not None:
                        trade_time = latest.get("trade_time", "")
                        # 收盘后，如果分钟数据时间 < 15:00，说明该数据不是最终收盘快照，
                        # 可能是低流动性ETF盘中最后成交时间（如14:30），
                        # 不应作为"最新价"展示，需 fallback 到日线收盘价
                        if market_closed and trade_time:
                            try:
                                time_part = (
                                    trade_time.split(" ")[-1]
                                    if " " in trade_time
                                    else trade_time
                                )
                                hhmm = int(time_part[:2]) * 100 + int(time_part[3:5])
                                if hhmm < 1500:
                                    # 跳过这个过期的分钟数据，让后续步骤用日线数据
                                    logger.debug(
                                        f"Skipping stale minute data for {code}: trade_time={trade_time}"
                                    )
                                    continue
                            except (ValueError, IndexError):
                                pass
                        prices[code] = {
                            "close": float(latest["close"]),
                            "trade_time": trade_time,
                            "prev_close": None,  # 将在步骤3补充
                        }
        except Exception as e:
            logger.warning(f"Failed to get prices from rt_minute cache: {e}")

        # 2. 对于缓存中没有（或被跳过）的代码，按需从 TuShare API 实时拉取
        missing_codes = [c for c in ts_codes if c not in prices]
        if missing_codes:
            try:
                on_demand_prices = self._fetch_ondemand_rt_prices(missing_codes)
                prices.update(on_demand_prices)
            except Exception as e:
                logger.warning(f"Failed to on-demand fetch prices: {e}")

        # 3. 仍未命中的 fallback 到 ClickHouse 日线表
        still_missing = [c for c in ts_codes if c not in prices]
        if still_missing and self.db is not None:
            try:
                for code in still_missing:
                    price_info = self._get_daily_latest_price(code)
                    if price_info:
                        prices[code] = price_info
            except Exception as e:
                logger.warning(f"Failed to batch get prices from database: {e}")

        # 4. 批量获取昨收价(prev_close)用于计算今日涨跌
        if prices and self.db is not None:
            await self._batch_fill_prev_close(prices)

        return prices

    def _fetch_ondemand_rt_prices(
        self, ts_codes: list[str]
    ) -> dict[str, dict[str, Any]]:
        """按需从 TuShare rt_min API 获取实时价格（用于缓存中不存在的持仓代码）。

        Returns dict mapping ts_code -> {'close': float, 'trade_time': str, 'prev_close': None}
        """
        import tushare as ts

        from stock_datasource.config.settings import settings as _settings

        result = {}
        if not _settings.TUSHARE_TOKEN:
            return result

        pro = ts.pro_api()
        now_dt = datetime.now()

        for code in ts_codes:
            try:
                # A股/ETF 用 rt_min，港股用 hk_mins
                if code.endswith(".HK"):
                    df = pro.hk_mins(
                        ts_code=code,
                        freq="1min",
                        start_date=now_dt.strftime("%Y-%m-%d 09:30:00"),
                        end_date=(
                            now_dt + __import__("datetime").timedelta(hours=1)
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                    )
                else:
                    df = pro.rt_min(ts_code=code, freq="1min")

                if df is not None and not df.empty:
                    last_row = df.iloc[-1]
                    close_val = float(last_row["close"])

                    # 解析时间
                    trade_time = ""
                    if "trade_time" in last_row.index:
                        tt = last_row["trade_time"]
                        if hasattr(tt, "strftime"):
                            trade_time = tt.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            trade_time = str(tt)

                    result[code] = {
                        "close": close_val,
                        "trade_time": trade_time,
                        "prev_close": None,
                    }
                    logger.info(
                        f"On-demand fetched {code}: price={close_val}, time={trade_time}"
                    )

                # 避免请求过快
                import time as _time

                _time.sleep(0.5)
            except Exception as e:
                logger.debug(f"On-demand fetch failed for {code}: {e}")

        return result

    def _get_daily_latest_price(self, ts_code: str) -> dict[str, Any] | None:
        """从 ClickHouse 日线表获取最新收盘价和日期。返回秒级精度的 trade_time。"""
        if self.db is None:
            return None
        try:
            market_type = self._infer_market_type(ts_code)

            # 按市场类型查询对应日线表
            queries = []
            if market_type == "index":
                queries.append(("ods_index_daily", "index"))
            elif market_type == "etf":
                queries.append(("ods_etf_fund_daily", "etf"))
            elif market_type == "hk":
                queries.append(("ods_hk_daily", "hk"))
            else:
                queries.append(("ods_daily", "a_stock"))

            for table, mtype in queries:
                query = f"""
                    SELECT close, trade_date, pre_close FROM {table}
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df = self.db.execute_query(query, {"code": ts_code})
                if not df.empty:
                    trade_date = df.iloc[0]["trade_date"]
                    trade_time = self._format_trade_datetime(
                        trade_date, market_type=mtype
                    )
                    prev_close = (
                        float(df.iloc[0]["pre_close"])
                        if "pre_close" in df.columns
                        and pd.notna(df.iloc[0]["pre_close"])
                        else None
                    )
                    return {
                        "close": float(df.iloc[0]["close"]),
                        "trade_time": trade_time,
                        "prev_close": prev_close,
                    }

            # Fallback: 如果推断不准，尝试所有表
            if market_type != "a_stock":
                df = self.db.execute_query(
                    "SELECT close, trade_date, pre_close FROM ods_daily WHERE ts_code = %(code)s ORDER BY trade_date DESC LIMIT 1",
                    {"code": ts_code},
                )
                if not df.empty:
                    trade_date = df.iloc[0]["trade_date"]
                    return {
                        "close": float(df.iloc[0]["close"]),
                        "trade_time": self._format_trade_datetime(trade_date),
                        "prev_close": float(df.iloc[0]["pre_close"])
                        if "pre_close" in df.columns
                        and pd.notna(df.iloc[0]["pre_close"])
                        else None,
                    }

            if market_type != "etf":
                df_etf = self.db.execute_query(
                    "SELECT close, trade_date, pre_close FROM ods_etf_fund_daily WHERE ts_code = %(code)s ORDER BY trade_date DESC LIMIT 1",
                    {"code": ts_code},
                )
                if not df_etf.empty:
                    trade_date = df_etf.iloc[0]["trade_date"]
                    return {
                        "close": float(df_etf.iloc[0]["close"]),
                        "trade_time": self._format_trade_datetime(
                            trade_date, market_type="etf"
                        ),
                        "prev_close": float(df_etf.iloc[0]["pre_close"])
                        if "pre_close" in df_etf.columns
                        and pd.notna(df_etf.iloc[0]["pre_close"])
                        else None,
                    }

            if market_type != "hk" and ts_code.endswith(".HK"):
                df_hk = self.db.execute_query(
                    "SELECT close, trade_date, pre_close FROM ods_hk_daily WHERE ts_code = %(code)s ORDER BY trade_date DESC LIMIT 1",
                    {"code": ts_code},
                )
                if not df_hk.empty:
                    trade_date = df_hk.iloc[0]["trade_date"]
                    return {
                        "close": float(df_hk.iloc[0]["close"]),
                        "trade_time": self._format_trade_datetime(
                            trade_date, market_type="hk"
                        ),
                        "prev_close": float(df_hk.iloc[0]["pre_close"])
                        if "pre_close" in df_hk.columns
                        and pd.notna(df_hk.iloc[0]["pre_close"])
                        else None,
                    }
        except Exception as e:
            logger.warning(f"Failed to get daily price for {ts_code}: {e}")
        return None

    @staticmethod
    def _format_trade_datetime(trade_date, market_type: str = "a_stock") -> str:
        """将日线 trade_date 格式化为秒级精度的 trade_time。

        日线数据没有精确到秒的时间戳，使用各市场收盘时间作为补充：
        - A股: 15:00:00
        - ETF: 15:00:00
        - 港股: 16:00:00 (16:08 收盘，取整 16:00)
        """
        if hasattr(trade_date, "strftime"):
            date_str = trade_date.strftime("%Y-%m-%d")
        else:
            date_str = str(trade_date)
            if len(date_str) == 8 and "-" not in date_str:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        close_time = "16:00:00" if market_type == "hk" else "15:00:00"
        return f"{date_str} {close_time}"

    async def _update_position_prices(
        self, position: Position, prices_cache: dict[str, Any] = None
    ):
        """Update position current price and calculations. Supports A-shares, ETFs and HK stocks.

        Priority: rt_minute_latest (realtime, second-precision) > ods_daily (daily close)

        After market close, stale minute data (time < 15:00) is skipped in favor of daily close.
        """
        market_closed = self._is_market_closed()
        updated = False
        # 1. 优先使用批量缓存的最新价格（已包含收盘后stale数据过滤逻辑）
        if prices_cache and position.ts_code in prices_cache:
            info = prices_cache[position.ts_code]
            position.current_price = info["close"]
            position.price_update_time = info.get("trade_time", "")
            position.prev_close = info.get("prev_close")
            updated = True
        else:
            # 2. 尝试单独从分钟缓存获取
            try:
                from stock_datasource.modules.realtime_minute.cache_store import (
                    get_cache_store,
                )

                cache = get_cache_store()
                if cache.available:
                    latest = cache.get_latest("", position.ts_code, "1min")
                    if latest and latest.get("close") is not None:
                        trade_time = latest.get("trade_time", "")
                        # 收盘后跳过过期的分钟数据
                        if market_closed and trade_time:
                            try:
                                time_part = (
                                    trade_time.split(" ")[-1]
                                    if " " in trade_time
                                    else trade_time
                                )
                                hhmm = int(time_part[:2]) * 100 + int(time_part[3:5])
                                if hhmm < 1500:
                                    logger.debug(
                                        f"Skipping stale minute data for {position.ts_code}: {trade_time}"
                                    )
                                    # Don't set updated=True, fall through to daily
                                    latest = None
                            except (ValueError, IndexError):
                                pass
                        if latest:
                            position.current_price = float(latest["close"])
                            position.price_update_time = trade_time
                            # rt_minute cache 没有 prev_close，从日线表补充
                            prev_close = self._get_prev_close_from_db(position.ts_code)
                            if prev_close is not None:
                                position.prev_close = prev_close
                            updated = True
            except Exception as e:
                logger.warning(
                    f"Failed to get price from rt_minute cache for {position.ts_code}: {e}"
                )

        # 3. 分钟缓存没有，fallback 到日线表
        if not updated:
            price_info = self._get_daily_latest_price(position.ts_code)
            if price_info:
                position.current_price = price_info["close"]
                position.price_update_time = price_info.get("trade_time", "")
                position.prev_close = price_info.get("prev_close")

        # Fallback: use cost_price if no price found
        if position.current_price is None:
            position.current_price = position.cost_price

        # Calculate market value and profit/loss
        if position.current_price:
            position.market_value = position.quantity * position.current_price
            cost_total = position.quantity * position.cost_price
            position.profit_loss = position.market_value - cost_total
            position.profit_rate = (
                (position.profit_loss / cost_total * 100) if cost_total > 0 else 0
            )

        # Calculate daily change (今日涨跌)
        if position.prev_close and position.prev_close > 0 and position.current_price:
            position.daily_change = position.current_price - position.prev_close
            position.daily_pct_chg = position.daily_change / position.prev_close * 100
        elif position.current_price and not position.prev_close:
            # 没有昨收价时，尝试从日线获取最近两日数据计算
            self._calc_daily_change_from_db(position)

    async def _batch_fill_prev_close(self, prices: dict[str, dict[str, Any]]):
        """批量补充昨收价(prev_close)用于今日涨跌计算。

        当日线数据缺失或过期时，主动触发对应市场的日线同步插件补数据，
        然后重新查询。

        核心逻辑：
        1. 先从DB查询 prev_close
        2. 批量检查所有持仓的日线数据是否新鲜
        3. 如果日线数据过期，触发同步补数据
        4. 同步后重新查询 prev_close
        """
        codes_need_prev = [
            code for code, info in prices.items() if info.get("prev_close") is None
        ]
        if not codes_need_prev or self.db is None:
            return
        try:
            # 第一次尝试：直接从DB查询
            for code in codes_need_prev:
                prev_close = self._get_prev_close_from_db(code)
                if prev_close is not None:
                    prices[code]["prev_close"] = prev_close

            # 批量检查所有代码的日线数据新鲜度（包括已获取到 prev_close 的）
            # 因为即使拿到了 prev_close，如果日线数据不是最新的，prev_close 可能不准
            all_codes = list(prices.keys())
            stale_codes = self._batch_check_markets_freshness(all_codes)

            # 触发缺失/过期的日线数据同步
            # stale_codes: {ts_code: market_type}，提取需要同步的市场类型
            if stale_codes:
                markets_to_sync = set(stale_codes.values())
                synced_markets = await self._trigger_daily_sync_for_markets(
                    markets_to_sync
                )
                if synced_markets:
                    # 同步后重新查询所有需要 prev_close 的代码
                    await asyncio.sleep(2)  # 等待数据写入
                    for code in codes_need_prev:
                        prev_close = self._get_prev_close_from_db(code)
                        if prev_close is not None:
                            prices[code]["prev_close"] = prev_close
                            logger.info(
                                f"Synced daily data, got prev_close for {code}: {prev_close}"
                            )
        except Exception as e:
            logger.warning(f"Failed to batch fill prev_close: {e}")

    @staticmethod
    def _infer_market_type(ts_code: str) -> str:
        """从 ts_code 推断市场类型: a_stock / etf / hk / index"""
        if not isinstance(ts_code, str) or len(ts_code) < 3:
            return "a_stock"
        if ts_code.endswith(".HK"):
            return "hk"
        # 指数: 000001.SH, 399001.SZ 等
        if ts_code.startswith(("0000", "3990", "3991", "3993", "3996", "3999")):
            # 区分指数和股票：指数通常是 000001.SH(上证指数) 或 399001.SZ(深证成指)
            # 但 000001.SZ 是平安银行，需要更精确判断
            suffix = ts_code[-2:]
            prefix = ts_code[:6]
            if suffix == "SH" and prefix.startswith("0000"):
                return "index"
            if suffix == "SZ" and prefix.startswith("399"):
                return "index"
        # ETF
        prefix = ts_code[:3]
        if prefix in (
            "510",
            "511",
            "512",
            "513",
            "515",
            "516",
            "518",
            "520",
            "560",
            "561",
            "562",
            "563",
            "588",
            "159",
            "150",
            "501",
            "502",
        ):
            return "etf"
        return "a_stock"

    @staticmethod
    def _get_daily_table_for_market(market_type: str) -> str:
        """市场类型对应的日线表名"""
        return {
            "a_stock": "ods_daily",
            "etf": "ods_etf_fund_daily",
            "hk": "ods_hk_daily",
            "index": "ods_index_daily",
        }.get(market_type, "ods_daily")

    @staticmethod
    def _get_plugin_name_for_market(market_type: str) -> str:
        """市场类型对应的日线同步插件名"""
        return {
            "a_stock": "tushare_daily",
            "etf": "tushare_etf_fund_daily",
            "hk": "tushare_hk_daily",
            "index": "tushare_index_daily",
        }.get(market_type, "tushare_daily")

    def _check_daily_data_fresh(self, ts_code: str) -> str | None:
        """检查某只股票的日线数据是否是最新的。

        Returns:
            None if data is fresh (latest daily date is the most recent trading day)
            market_type string if data is stale or missing, indicating which market needs sync
        """
        if self.db is None:
            return None

        market_type = self._infer_market_type(ts_code)
        table = self._get_daily_table_for_market(market_type)

        try:
            query = f"""
                SELECT trade_date FROM {table}
                WHERE ts_code = %(code)s
                ORDER BY trade_date DESC LIMIT 1
            """
            df = self.db.execute_query(query, {"code": ts_code})

            if df.empty:
                logger.info(
                    f"No daily data found for {ts_code} in {table}, need sync ({market_type})"
                )
                return market_type

            latest_date = df.iloc[0]["trade_date"]
            if hasattr(latest_date, "strftime"):
                latest_str = latest_date.strftime("%Y-%m-%d")
            else:
                latest_str = str(latest_date)[:10]

            latest_trading_day = self._get_latest_trading_day(market_type)
            if latest_trading_day and latest_str < latest_trading_day:
                logger.info(
                    f"Daily data stale for {ts_code}: latest={latest_str}, "
                    f"latest_trading_day={latest_trading_day}, need sync ({market_type})"
                )
                return market_type
        except Exception as e:
            logger.warning(f"Failed to check daily data freshness for {ts_code}: {e}")

        return None

    def _get_latest_trading_day(self, market_type: str) -> str | None:
        """获取指定市场最近一个已过去的交易日。

        Returns:
            YYYY-MM-DD 格式的交易日字符串，或 None
        """
        try:
            from datetime import date as date_cls

            from stock_datasource.core.trade_calendar import trade_calendar_service

            market_key = "hk" if market_type == "hk" else "cn"
            recent_days = trade_calendar_service.get_trading_days(
                n=5, market=market_key
            )
            if recent_days:
                today = date_cls.today()
                for day in recent_days:
                    try:
                        d = datetime.strptime(day, "%Y-%m-%d").date()
                        if d < today:
                            return day
                    except ValueError:
                        continue
        except Exception as e:
            logger.debug(f"Could not get latest trading day: {e}")
        return None

    def _batch_check_markets_freshness(self, ts_codes: list[str]) -> dict[str, str]:
        """批量检查多个代码的日线数据新鲜度，按市场类型分组查询。

        每个市场只查一次全局最新日期，避免逐个代码查询。

        Returns:
            {ts_code: market_type} 需要同步的代码及其市场类型
        """
        if self.db is None or not ts_codes:
            return {}

        # 按市场类型分组
        market_groups: dict[str, list[str]] = {}
        for code in ts_codes:
            mt = self._infer_market_type(code)
            if mt not in market_groups:
                market_groups[mt] = []
            market_groups[mt].append(code)

        stale_codes: dict[str, str] = {}  # ts_code -> market_type

        for market_type, codes in market_groups.items():
            table = self._get_daily_table_for_market(market_type)

            try:
                # 查该市场日线表的全局最新日期（一条SQL）
                query = f"SELECT max(trade_date) as latest FROM {table}"
                df = self.db.execute_query(query)

                if df.empty or pd.isna(df.iloc[0]["latest"]):
                    for code in codes:
                        stale_codes[code] = market_type
                    logger.info(
                        f"Table {table} has no data, {len(codes)} codes need sync ({market_type})"
                    )
                    continue

                global_latest = df.iloc[0]["latest"]
                if hasattr(global_latest, "strftime"):
                    global_latest_str = global_latest.strftime("%Y-%m-%d")
                else:
                    global_latest_str = str(global_latest)[:10]

                latest_trading_day = self._get_latest_trading_day(market_type)

                if latest_trading_day and global_latest_str < latest_trading_day:
                    for code in codes:
                        stale_codes[code] = market_type
                    logger.info(
                        f"Daily data stale for {market_type}: table_latest={global_latest_str}, "
                        f"latest_trading_day={latest_trading_day}, {len(codes)} codes need sync"
                    )

            except Exception as e:
                # 表不存在或查询失败，也标记为需要同步（可能是表未建或数据未同步）
                for code in codes:
                    stale_codes[code] = market_type
                logger.warning(
                    f"Failed to check freshness for {market_type} (table={table}): {e}, marking {len(codes)} codes as stale"
                )

        return stale_codes

    async def _trigger_daily_sync_for_markets(self, market_types: set) -> set:
        """直接触发指定市场的日线数据同步。

        不再重复检查新鲜度，因为调用方已经通过 _batch_check_markets_freshness 确认过了。

        Args:
            market_types: 需要同步的市场类型集合，如 {"a_stock", "etf", "hk", "index"}

        Returns:
            已触发同步成功的市场类型集合
        """
        if not market_types:
            return set()

        synced = set()
        for market_type in market_types:
            try:
                plugin_name = self._get_plugin_name_for_market(market_type)
                logger.info(
                    f"Triggering daily sync for {market_type} via plugin {plugin_name}"
                )

                from stock_datasource.core.plugin_manager import plugin_manager

                plugin = plugin_manager.get_plugin(plugin_name)
                if plugin and plugin.is_enabled():
                    # 获取目标交易日（最近一个已过去的交易日）
                    target_date = self._get_latest_trading_day(market_type)

                    if not target_date:
                        logger.warning(
                            f"Cannot determine target trade date for {market_type} sync"
                        )
                        continue

                    target_date_compact = target_date.replace("-", "")
                    logger.info(f"Syncing {market_type} daily data for {target_date}")

                    # 对港股用 start_date/end_date，其他用 trade_date
                    if market_type == "hk":
                        result = await asyncio.to_thread(
                            plugin.run,
                            start_date=target_date_compact,
                            end_date=target_date_compact,
                        )
                    else:
                        result = await asyncio.to_thread(
                            plugin.run, trade_date=target_date_compact
                        )

                    if result and result.get("status") == "success":
                        load_info = result.get("steps", {}).get("load", {})
                        records = (
                            load_info.get("total_records", 0)
                            if isinstance(load_info, dict)
                            else 0
                        )
                        logger.info(
                            f"Daily sync succeeded for {market_type}: {records} records"
                        )
                        synced.add(market_type)
                    else:
                        error = (
                            result.get("error", "unknown") if result else "no result"
                        )
                        logger.warning(f"Daily sync failed for {market_type}: {error}")
                else:
                    logger.warning(f"Plugin {plugin_name} not available or disabled")
            except Exception as e:
                logger.warning(f"Failed to trigger daily sync for {market_type}: {e}")

        return synced

    def _get_prev_close_from_db(self, ts_code: str) -> float | None:
        """从日线表获取昨收价（最新交易日的 close，即"今天"的前收）。

        注意：不能用最新日线记录的 pre_close 字段，因为中间可能有非交易日，
        pre_close 指的是那条记录自身的前收（可能隔了好几天），而非"今天的昨收"。
        正确的昨收 = 最近一个交易日的收盘价(close)。
        """
        if self.db is None:
            return None
        try:
            market_type = self._infer_market_type(ts_code)

            # 指数日线
            if market_type == "index":
                query_idx = """
                    SELECT close FROM ods_index_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df_idx = self.db.execute_query(query_idx, {"code": ts_code})
                if (
                    not df_idx.empty
                    and "close" in df_idx.columns
                    and pd.notna(df_idx.iloc[0]["close"])
                ):
                    return float(df_idx.iloc[0]["close"])

            # A股
            if market_type == "a_stock":
                query = """
                    SELECT close FROM ods_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df = self.db.execute_query(query, {"code": ts_code})
                if (
                    not df.empty
                    and "close" in df.columns
                    and pd.notna(df.iloc[0]["close"])
                ):
                    return float(df.iloc[0]["close"])

            # ETF
            if market_type == "etf":
                query_etf = """
                    SELECT close FROM ods_etf_fund_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df_etf = self.db.execute_query(query_etf, {"code": ts_code})
                if (
                    not df_etf.empty
                    and "close" in df_etf.columns
                    and pd.notna(df_etf.iloc[0]["close"])
                ):
                    return float(df_etf.iloc[0]["close"])

            # 港股
            if market_type == "hk":
                query_hk = """
                    SELECT close FROM ods_hk_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df_hk = self.db.execute_query(query_hk, {"code": ts_code})
                if (
                    not df_hk.empty
                    and "close" in df_hk.columns
                    and pd.notna(df_hk.iloc[0]["close"])
                ):
                    return float(df_hk.iloc[0]["close"])

            # Fallback: 如果 market_type 推断不准，按原顺序尝试所有表
            if market_type not in ("a_stock",):
                query = """
                    SELECT close FROM ods_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df = self.db.execute_query(query, {"code": ts_code})
                if (
                    not df.empty
                    and "close" in df.columns
                    and pd.notna(df.iloc[0]["close"])
                ):
                    return float(df.iloc[0]["close"])

            if market_type not in ("etf",):
                query_etf = """
                    SELECT close FROM ods_etf_fund_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df_etf = self.db.execute_query(query_etf, {"code": ts_code})
                if (
                    not df_etf.empty
                    and "close" in df_etf.columns
                    and pd.notna(df_etf.iloc[0]["close"])
                ):
                    return float(df_etf.iloc[0]["close"])

            if market_type not in ("hk",) and ts_code.endswith(".HK"):
                query_hk = """
                    SELECT close FROM ods_hk_daily 
                    WHERE ts_code = %(code)s 
                    ORDER BY trade_date DESC LIMIT 1
                """
                df_hk = self.db.execute_query(query_hk, {"code": ts_code})
                if (
                    not df_hk.empty
                    and "close" in df_hk.columns
                    and pd.notna(df_hk.iloc[0]["close"])
                ):
                    return float(df_hk.iloc[0]["close"])
        except Exception as e:
            logger.warning(f"Failed to get prev_close for {ts_code}: {e}")
        return None

    def _calc_daily_change_from_db(self, position: Position):
        """从DB获取最近两日收盘价来计算今日涨跌。"""
        if self.db is None or not position.ts_code:
            return
        try:
            market_type = self._infer_market_type(position.ts_code)

            # 按市场类型查询
            table_map = {
                "index": "ods_index_daily",
                "etf": "ods_etf_fund_daily",
                "hk": "ods_hk_daily",
                "a_stock": "ods_daily",
            }
            table = table_map.get(market_type, "ods_daily")

            query = f"""
                SELECT close, trade_date FROM {table}
                WHERE ts_code = %(code)s 
                ORDER BY trade_date DESC LIMIT 2
            """
            df = self.db.execute_query(query, {"code": position.ts_code})
            if len(df) >= 2:
                latest_close = float(df.iloc[0]["close"])
                prev_close = float(df.iloc[1]["close"])
                if prev_close > 0:
                    position.prev_close = prev_close
                    position.daily_change = latest_close - prev_close
                    position.daily_pct_chg = position.daily_change / prev_close * 100
                return

            # Fallback: 尝试其他表
            for fallback_table in [
                "ods_daily",
                "ods_etf_fund_daily",
                "ods_hk_daily",
                "ods_index_daily",
            ]:
                if fallback_table == table:
                    continue
                if fallback_table == "ods_hk_daily" and not position.ts_code.endswith(
                    ".HK"
                ):
                    continue
                try:
                    query_fb = f"""
                        SELECT close, trade_date FROM {fallback_table}
                        WHERE ts_code = %(code)s 
                        ORDER BY trade_date DESC LIMIT 2
                    """
                    df_fb = self.db.execute_query(query_fb, {"code": position.ts_code})
                    if len(df_fb) >= 2:
                        latest_close = float(df_fb.iloc[0]["close"])
                        prev_close = float(df_fb.iloc[1]["close"])
                        if prev_close > 0:
                            position.prev_close = prev_close
                            position.daily_change = latest_close - prev_close
                            position.daily_pct_chg = (
                                position.daily_change / prev_close * 100
                            )
                        return
                except Exception:
                    continue
        except Exception as e:
            logger.warning(
                f"Failed to calc daily change from DB for {position.ts_code}: {e}"
            )

    async def _batch_update_positions(
        self, positions: list[Position], user_id: str = "default_user"
    ):
        """Batch update positions in database with latest prices."""
        if not self.db or not positions:
            return

        try:
            # Since we're using ReplacingMergeTree, we need to insert full records
            # The engine will automatically deduplicate based on ORDER BY keys
            for position in positions:
                query = """
                    INSERT INTO user_positions 
                    (id, user_id, ts_code, stock_name, quantity, cost_price, buy_date, 
                     current_price, market_value, profit_loss, profit_rate, notes, updated_at)
                    VALUES (%(id)s, %(user_id)s, %(ts_code)s, %(stock_name)s, %(quantity)s, %(cost_price)s, 
                            %(buy_date)s, %(current_price)s, %(market_value)s, 
                            %(profit_loss)s, %(profit_rate)s, %(notes)s, %(updated_at)s)
                """
                params = {
                    "id": position.id,
                    "user_id": user_id,
                    "ts_code": position.ts_code,
                    "stock_name": position.stock_name,
                    "quantity": position.quantity,
                    "cost_price": position.cost_price,
                    "buy_date": position.buy_date,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "profit_loss": position.profit_loss,
                    "profit_rate": position.profit_rate,
                    "notes": position.notes,
                    "updated_at": datetime.now(),
                }
                self.db.execute(query, params)

            logger.info(f"Batch updated {len(positions)} positions for user {user_id}")

        except Exception as e:
            logger.warning(f"Failed to batch update positions: {e}")


# Global service instance
_portfolio_service = None


def get_portfolio_service() -> PortfolioService:
    """Get portfolio service instance."""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service
