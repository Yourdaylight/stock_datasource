"""Paper Trading Service — 模拟盘核心业务逻辑"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.strategies.base import TradingSignal
from stock_datasource.strategies.builtin.market_regime_strategy import RegimeState

from .schemas import (
    AccountSummary,
    CreateAccountRequest,
    EquityPoint,
    PerformanceMetrics,
    Position,
    TradeRecord,
    TradeResult,
)

logger = logging.getLogger(__name__)

# 手续费率
COMMISSION_RATE = 0.0003  # 万三
MIN_COMMISSION = 5.0  # 最低5元


class PaperTradingService:
    """模拟盘核心服务"""

    def __init__(self):
        self._db = db_client
        self._ensure_tables()

    # ------------------------------------------------------------------
    # 建表
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        """确保 ClickHouse 表存在"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS paper_trading_accounts (
                user_id String,
                account_id String,
                account_name String,
                initial_capital Float64 DEFAULT 1000000,
                current_cash Float64,
                strategy_id String DEFAULT 'stock_timing',
                status String DEFAULT 'active',
                created_at DateTime DEFAULT now(),
                updated_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY (user_id, account_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS paper_trading_positions (
                user_id String,
                account_id String,
                ts_code String,
                quantity Int32,
                avg_cost Float64,
                current_price Float64 DEFAULT 0,
                unrealized_pnl Float64 DEFAULT 0,
                first_buy_date Date,
                last_update DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(last_update)
            ORDER BY (user_id, account_id, ts_code)
            """,
            """
            CREATE TABLE IF NOT EXISTS paper_trading_trades (
                user_id String,
                account_id String,
                trade_id String,
                ts_code String,
                direction String,
                quantity Int32,
                price Float64,
                amount Float64,
                commission Float64,
                signal_reason String DEFAULT '',
                signal_confidence Float64 DEFAULT 0,
                regime_state String DEFAULT '',
                trade_date Date,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (user_id, account_id, trade_date, trade_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS paper_trading_daily_snapshots (
                user_id String,
                account_id String,
                snapshot_date Date,
                total_value Float64,
                cash Float64,
                positions_value Float64,
                daily_pnl Float64 DEFAULT 0,
                total_pnl Float64 DEFAULT 0,
                total_return Float64 DEFAULT 0,
                position_count Int32 DEFAULT 0,
                regime String DEFAULT '',
                position_level Float64 DEFAULT 0,
                created_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(created_at)
            ORDER BY (user_id, account_id, snapshot_date)
            """,
        ]
        for sql in tables:
            try:
                self._db.execute(sql)
            except Exception as e:
                logger.debug(f"Table creation (may already exist): {e}")

    # ------------------------------------------------------------------
    # 账户管理
    # ------------------------------------------------------------------

    async def create_account(
        self, user_id: str, request: CreateAccountRequest
    ) -> AccountSummary:
        """创建模拟账户"""
        account_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        row = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "account_name": request.account_name,
                    "initial_capital": request.initial_capital,
                    "current_cash": request.initial_capital,
                    "strategy_id": request.strategy_id,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_accounts", row)

        return AccountSummary(
            account_id=account_id,
            account_name=request.account_name,
            initial_capital=request.initial_capital,
            current_cash=request.initial_capital,
            total_value=request.initial_capital,
            total_return_pct=0.0,
            position_count=0,
            status="active",
            created_at=now.isoformat(),
        )

    async def get_accounts(self, user_id: str) -> list[AccountSummary]:
        """获取用户所有模拟账户"""
        sql = f"""
            SELECT * FROM paper_trading_accounts FINAL
            WHERE user_id = '{user_id}'
            ORDER BY created_at DESC
        """
        df = self._db.execute_query(sql)
        if df is None or df.empty:
            return []

        accounts = []
        for _, row in df.iterrows():
            accounts.append(
                AccountSummary(
                    account_id=row["account_id"],
                    account_name=row["account_name"],
                    initial_capital=float(row["initial_capital"]),
                    current_cash=float(row["current_cash"]),
                    status=row["status"],
                    created_at=str(row.get("created_at", "")),
                )
            )
        return accounts

    async def get_account(self, user_id: str, account_id: str) -> AccountSummary | None:
        """获取账户详情"""
        sql = f"""
            SELECT * FROM paper_trading_accounts FINAL
            WHERE user_id = '{user_id}' AND account_id = '{account_id}'
            LIMIT 1
        """
        df = self._db.execute_query(sql)
        if df is None or df.empty:
            return None

        row = df.iloc[0]
        positions = await self.get_positions(user_id, account_id)
        positions_value = sum(p.market_value for p in positions)
        cash = float(row["current_cash"])
        total_value = cash + positions_value
        initial = float(row["initial_capital"])
        total_return = (total_value - initial) / initial * 100 if initial > 0 else 0

        return AccountSummary(
            account_id=account_id,
            account_name=row["account_name"],
            initial_capital=initial,
            current_cash=cash,
            total_value=total_value,
            total_return_pct=round(total_return, 2),
            position_count=len(positions),
            status=row["status"],
            created_at=str(row.get("created_at", "")),
        )

    # ------------------------------------------------------------------
    # 持仓管理
    # ------------------------------------------------------------------

    async def get_positions(self, user_id: str, account_id: str) -> list[Position]:
        """获取持仓列表"""
        sql = f"""
            SELECT * FROM paper_trading_positions FINAL
            WHERE user_id = '{user_id}' AND account_id = '{account_id}'
              AND quantity > 0
        """
        df = self._db.execute_query(sql)
        if df is None or df.empty:
            return []

        positions = []
        for _, row in df.iterrows():
            qty = int(row["quantity"])
            avg_cost = float(row["avg_cost"])
            current_price = float(row.get("current_price", avg_cost))
            market_value = qty * current_price
            unrealized_pnl = (current_price - avg_cost) * qty
            pnl_pct = (current_price / avg_cost - 1) * 100 if avg_cost > 0 else 0

            positions.append(
                Position(
                    ts_code=row["ts_code"],
                    quantity=qty,
                    avg_cost=round(avg_cost, 3),
                    current_price=round(current_price, 2),
                    market_value=round(market_value, 2),
                    unrealized_pnl=round(unrealized_pnl, 2),
                    unrealized_pnl_pct=round(pnl_pct, 2),
                    first_buy_date=str(row.get("first_buy_date", "")),
                )
            )
        return positions

    # ------------------------------------------------------------------
    # 账户状态管理
    # ------------------------------------------------------------------

    async def update_account_status(
        self, user_id: str, account_id: str, new_status: str
    ) -> None:
        """更新账户状态 (active/paused/closed)"""
        sql = f"""
            SELECT * FROM paper_trading_accounts FINAL
            WHERE user_id = '{user_id}' AND account_id = '{account_id}'
            LIMIT 1
        """
        existing = self._db.execute_query(sql)
        if existing is not None and not existing.empty:
            update_row = existing.iloc[0].to_dict()
            update_row["status"] = new_status
            update_row["updated_at"] = datetime.now()
            self._db.insert_dataframe(
                "paper_trading_accounts", pd.DataFrame([update_row])
            )

    # ------------------------------------------------------------------
    # 交易执行
    # ------------------------------------------------------------------

    async def execute_signal(
        self,
        user_id: str,
        account_id: str,
        signal: TradingSignal,
        regime: RegimeState | None = None,
    ) -> TradeResult:
        """将策略信号转化为模拟交易"""
        # 获取账户
        account = await self.get_account(user_id, account_id)
        if not account:
            return TradeResult(success=False, message="账户不存在")
        if account.status != "active":
            return TradeResult(success=False, message="账户已暂停")

        if signal.action == "buy":
            return await self._execute_buy(
                user_id, account_id, signal, regime, account.current_cash
            )
        elif signal.action == "sell":
            return await self._execute_sell(user_id, account_id, signal, regime)
        else:
            return TradeResult(success=False, message=f"无效操作: {signal.action}")

    async def _execute_buy(
        self,
        user_id: str,
        account_id: str,
        signal: TradingSignal,
        regime: RegimeState | None,
        available_cash: float,
    ) -> TradeResult:
        """执行买入"""
        price = signal.price
        confidence = signal.confidence

        # 计算可买金额：可用现金 × confidence (作为仓位比例)
        buy_amount = available_cash * min(confidence, 0.3)  # 单笔最多30%资金
        quantity = int(buy_amount / price / 100) * 100  # 100股整数倍

        if quantity < 100:
            return TradeResult(success=False, message="资金不足，无法买入最小手数")

        amount = quantity * price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        total_cost = amount + commission

        if total_cost > available_cash:
            quantity -= 100
            if quantity < 100:
                return TradeResult(success=False, message="扣除手续费后资金不足")
            amount = quantity * price
            commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
            total_cost = amount + commission

        trade_id = str(uuid.uuid4())[:8]
        today = date.today()

        # 记录交易
        trade_df = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "trade_id": trade_id,
                    "ts_code": signal.symbol,
                    "direction": "buy",
                    "quantity": quantity,
                    "price": price,
                    "amount": amount,
                    "commission": commission,
                    "signal_reason": signal.reason,
                    "signal_confidence": confidence,
                    "regime_state": regime.regime if regime else "",
                    "trade_date": today,
                    "created_at": datetime.now(),
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_trades", trade_df)

        # 更新持仓
        await self._update_position_after_buy(
            user_id, account_id, signal.symbol, quantity, price, today
        )

        # 更新账户现金
        new_cash = available_cash - total_cost
        self._update_account_cash(user_id, account_id, new_cash)

        logger.info(
            f"Paper trade BUY: {signal.symbol} × {quantity} @ {price:.2f} "
            f"(confidence={confidence:.2f}, regime={regime.regime if regime else 'N/A'})"
        )

        return TradeResult(
            success=True,
            trade_id=trade_id,
            message=f"买入 {signal.symbol} {quantity}股 @ {price:.2f}",
            executed_quantity=quantity,
            executed_price=price,
            commission=commission,
        )

    async def _execute_sell(
        self,
        user_id: str,
        account_id: str,
        signal: TradingSignal,
        regime: RegimeState | None,
    ) -> TradeResult:
        """执行卖出"""
        # 查询当前持仓
        positions = await self.get_positions(user_id, account_id)
        position = next((p for p in positions if p.ts_code == signal.symbol), None)

        if not position or position.quantity <= 0:
            return TradeResult(success=False, message=f"无持仓: {signal.symbol}")

        price = signal.price
        quantity = position.quantity  # 全部卖出
        amount = quantity * price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        proceeds = amount - commission

        trade_id = str(uuid.uuid4())[:8]
        today = date.today()

        # 记录交易
        trade_df = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "trade_id": trade_id,
                    "ts_code": signal.symbol,
                    "direction": "sell",
                    "quantity": quantity,
                    "price": price,
                    "amount": amount,
                    "commission": commission,
                    "signal_reason": signal.reason,
                    "signal_confidence": signal.confidence,
                    "regime_state": regime.regime if regime else "",
                    "trade_date": today,
                    "created_at": datetime.now(),
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_trades", trade_df)

        # 清除持仓（设quantity=0）
        await self._clear_position(user_id, account_id, signal.symbol)

        # 更新账户现金
        account = await self.get_account(user_id, account_id)
        if account:
            new_cash = account.current_cash + proceeds
            self._update_account_cash(user_id, account_id, new_cash)

        logger.info(
            f"Paper trade SELL: {signal.symbol} × {quantity} @ {price:.2f} "
            f"(reason={signal.reason})"
        )

        return TradeResult(
            success=True,
            trade_id=trade_id,
            message=f"卖出 {signal.symbol} {quantity}股 @ {price:.2f}",
            executed_quantity=quantity,
            executed_price=price,
            commission=commission,
        )

    # ------------------------------------------------------------------
    # 持仓更新辅助
    # ------------------------------------------------------------------

    async def _update_position_after_buy(
        self,
        user_id: str,
        account_id: str,
        ts_code: str,
        quantity: int,
        price: float,
        buy_date: date,
    ) -> None:
        """买入后更新持仓"""
        # 查询已有持仓
        sql = f"""
            SELECT quantity, avg_cost, first_buy_date
            FROM paper_trading_positions FINAL
            WHERE user_id = '{user_id}'
              AND account_id = '{account_id}'
              AND ts_code = '{ts_code}'
              AND quantity > 0
            LIMIT 1
        """
        df = self._db.execute_query(sql)

        if df is not None and not df.empty:
            # 已有持仓 → 加仓
            existing_qty = int(df.iloc[0]["quantity"])
            existing_cost = float(df.iloc[0]["avg_cost"])
            first_date = df.iloc[0]["first_buy_date"]

            new_qty = existing_qty + quantity
            new_avg_cost = (
                (existing_qty * existing_cost + quantity * price) / new_qty
            )
        else:
            new_qty = quantity
            new_avg_cost = price
            first_date = buy_date

        pos_df = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "ts_code": ts_code,
                    "quantity": new_qty,
                    "avg_cost": new_avg_cost,
                    "current_price": price,
                    "unrealized_pnl": 0.0,
                    "first_buy_date": first_date,
                    "last_update": datetime.now(),
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_positions", pos_df)

    async def _clear_position(
        self, user_id: str, account_id: str, ts_code: str
    ) -> None:
        """清除持仓（设为0）"""
        pos_df = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "ts_code": ts_code,
                    "quantity": 0,
                    "avg_cost": 0.0,
                    "current_price": 0.0,
                    "unrealized_pnl": 0.0,
                    "first_buy_date": date.today(),
                    "last_update": datetime.now(),
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_positions", pos_df)

    def _update_account_cash(
        self, user_id: str, account_id: str, new_cash: float
    ) -> None:
        """更新账户现金"""
        row = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "account_name": "",  # ReplacingMergeTree 需要所有 ORDER BY 之外的列
                    "initial_capital": 0,
                    "current_cash": new_cash,
                    "strategy_id": "",
                    "status": "active",
                    "created_at": datetime(2000, 1, 1),  # 旧时间戳不覆盖 name 等
                    "updated_at": datetime.now(),
                }
            ]
        )
        # 用 FINAL 查重建完整行再插入
        sql = f"""
            SELECT * FROM paper_trading_accounts FINAL
            WHERE user_id = '{user_id}' AND account_id = '{account_id}'
            LIMIT 1
        """
        existing = self._db.execute_query(sql)
        if existing is not None and not existing.empty:
            update_row = existing.iloc[0].to_dict()
            update_row["current_cash"] = new_cash
            update_row["updated_at"] = datetime.now()
            self._db.insert_dataframe(
                "paper_trading_accounts", pd.DataFrame([update_row])
            )

    # ------------------------------------------------------------------
    # 交易记录查询
    # ------------------------------------------------------------------

    async def get_trades(
        self, user_id: str, account_id: str, days: int = 30
    ) -> list[TradeRecord]:
        """获取交易记录"""
        sql = f"""
            SELECT * FROM paper_trading_trades
            WHERE user_id = '{user_id}'
              AND account_id = '{account_id}'
              AND trade_date >= today() - {days}
            ORDER BY trade_date DESC, created_at DESC
            LIMIT 100
        """
        df = self._db.execute_query(sql)
        if df is None or df.empty:
            return []

        return [
            TradeRecord(
                trade_id=row["trade_id"],
                ts_code=row["ts_code"],
                direction=row["direction"],
                quantity=int(row["quantity"]),
                price=float(row["price"]),
                amount=float(row["amount"]),
                commission=float(row.get("commission", 0)),
                signal_reason=row.get("signal_reason", ""),
                signal_confidence=float(row.get("signal_confidence", 0)),
                regime_state=row.get("regime_state", ""),
                trade_date=str(row["trade_date"]),
            )
            for _, row in df.iterrows()
        ]

    # ------------------------------------------------------------------
    # 每日快照
    # ------------------------------------------------------------------

    async def mark_to_market(self, user_id: str, account_id: str) -> None:
        """按最新收盘价更新所有持仓的 current_price 和 unrealized_pnl"""
        positions = await self.get_positions(user_id, account_id)
        if not positions:
            return

        ts_codes = [p.ts_code for p in positions]
        codes_str = ", ".join(f"'{c}'" for c in ts_codes)

        # 查询每只股票最新收盘价
        sql = f"""
            SELECT ts_code, close
            FROM ods_daily
            WHERE ts_code IN ({codes_str})
            ORDER BY ts_code, trade_date DESC
            LIMIT 1 BY ts_code
        """
        try:
            price_df = self._db.execute_query(sql)
        except Exception as e:
            logger.warning(f"Mark-to-market query failed: {e}")
            return

        if price_df is None or price_df.empty:
            return

        latest_prices = dict(zip(price_df["ts_code"], price_df["close"].astype(float)))

        # 更新每个持仓的 current_price
        for pos in positions:
            new_price = latest_prices.get(pos.ts_code)
            if new_price is None or new_price <= 0:
                continue

            unrealized_pnl = (new_price - pos.avg_cost) * pos.quantity

            pos_df = pd.DataFrame(
                [
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "ts_code": pos.ts_code,
                        "quantity": pos.quantity,
                        "avg_cost": pos.avg_cost,
                        "current_price": new_price,
                        "unrealized_pnl": unrealized_pnl,
                        "first_buy_date": pos.first_buy_date,
                        "last_update": datetime.now(),
                    }
                ]
            )
            self._db.insert_dataframe("paper_trading_positions", pos_df)

    async def take_daily_snapshot(
        self,
        user_id: str,
        account_id: str,
        regime: RegimeState | None = None,
    ) -> None:
        """记录每日净值快照（先按市价更新持仓）"""
        # 先刷新市价
        await self.mark_to_market(user_id, account_id)

        account = await self.get_account(user_id, account_id)
        if not account:
            return

        positions = await self.get_positions(user_id, account_id)
        positions_value = sum(p.market_value for p in positions)
        total_value = account.current_cash + positions_value
        total_pnl = total_value - account.initial_capital
        total_return = total_pnl / account.initial_capital if account.initial_capital > 0 else 0

        # 获取昨日快照计算日收益
        yesterday_sql = f"""
            SELECT total_value FROM paper_trading_daily_snapshots FINAL
            WHERE user_id = '{user_id}'
              AND account_id = '{account_id}'
              AND snapshot_date < today()
            ORDER BY snapshot_date DESC
            LIMIT 1
        """
        yesterday_df = self._db.execute_query(yesterday_sql)
        daily_pnl = 0.0
        if yesterday_df is not None and not yesterday_df.empty:
            yesterday_value = float(yesterday_df.iloc[0]["total_value"])
            daily_pnl = total_value - yesterday_value

        snapshot_df = pd.DataFrame(
            [
                {
                    "user_id": user_id,
                    "account_id": account_id,
                    "snapshot_date": date.today(),
                    "total_value": total_value,
                    "cash": account.current_cash,
                    "positions_value": positions_value,
                    "daily_pnl": daily_pnl,
                    "total_pnl": total_pnl,
                    "total_return": total_return,
                    "position_count": len(positions),
                    "regime": regime.regime if regime else "",
                    "position_level": regime.position_level if regime else 0,
                    "created_at": datetime.now(),
                }
            ]
        )
        self._db.insert_dataframe("paper_trading_daily_snapshots", snapshot_df)

    # ------------------------------------------------------------------
    # 绩效查询
    # ------------------------------------------------------------------

    async def get_equity_curve(
        self, user_id: str, account_id: str, days: int = 90
    ) -> list[EquityPoint]:
        """获取净值曲线"""
        sql = f"""
            SELECT * FROM paper_trading_daily_snapshots FINAL
            WHERE user_id = '{user_id}'
              AND account_id = '{account_id}'
              AND snapshot_date >= today() - {days}
            ORDER BY snapshot_date ASC
        """
        df = self._db.execute_query(sql)
        if df is None or df.empty:
            return []

        # 获取 initial_capital 计算收益率
        account = await self.get_account(user_id, account_id)
        initial = account.initial_capital if account else 1000000

        return [
            EquityPoint(
                date=str(row["snapshot_date"]),
                total_value=float(row["total_value"]),
                cash=float(row["cash"]),
                positions_value=float(row["positions_value"]),
                daily_pnl=float(row.get("daily_pnl", 0)),
                total_return_pct=round(
                    (float(row["total_value"]) - initial) / initial * 100, 2
                ),
            )
            for _, row in df.iterrows()
        ]

    async def get_performance(
        self, user_id: str, account_id: str
    ) -> PerformanceMetrics:
        """计算绩效指标"""
        # 获取所有快照
        sql = f"""
            SELECT total_value, snapshot_date FROM paper_trading_daily_snapshots FINAL
            WHERE user_id = '{user_id}' AND account_id = '{account_id}'
            ORDER BY snapshot_date ASC
        """
        snapshots = self._db.execute_query(sql)

        # 获取所有交易
        trades = await self.get_trades(user_id, account_id, days=365)
        account = await self.get_account(user_id, account_id)
        initial = account.initial_capital if account else 1000000

        metrics = PerformanceMetrics(total_trades=len(trades))

        if snapshots is not None and len(snapshots) > 1:
            values = snapshots["total_value"].astype(float).values
            returns = np.diff(values) / values[:-1]

            # 总收益
            metrics.total_return_pct = round(
                (values[-1] - initial) / initial * 100, 2
            )

            # 年化收益
            days_count = len(values)
            if days_count > 1:
                annual_factor = 252 / days_count
                metrics.annual_return_pct = round(
                    ((values[-1] / initial) ** annual_factor - 1) * 100, 2
                )

            # 最大回撤
            peak = np.maximum.accumulate(values)
            drawdown = (values - peak) / peak
            metrics.max_drawdown_pct = round(float(np.min(drawdown)) * 100, 2)

            # Sharpe
            if len(returns) > 0 and np.std(returns) > 0:
                metrics.sharpe_ratio = round(
                    float(np.mean(returns) / np.std(returns) * np.sqrt(252)), 2
                )

        # 胜率统计 (FIFO 配对：每只股票按时间顺序配对买卖)
        if trades:
            from collections import defaultdict

            # 按股票分组，按时间排序
            buy_queue: dict[str, list[float]] = defaultdict(list)
            wins = 0
            losses = 0

            # trades 已按 trade_date DESC 排列，需要反转为 ASC
            sorted_trades = sorted(trades, key=lambda t: t.trade_date)
            for t in sorted_trades:
                if t.direction == "buy":
                    buy_queue[t.ts_code].append(float(t.price))
                elif t.direction == "sell" and buy_queue[t.ts_code]:
                    # FIFO: 匹配最早的买入
                    buy_price = buy_queue[t.ts_code].pop(0)
                    if t.price > buy_price:
                        wins += 1
                    else:
                        losses += 1

            total_pairs = wins + losses
            if total_pairs > 0:
                metrics.win_rate = round(wins / total_pairs * 100, 1)
                metrics.winning_trades = wins
                metrics.losing_trades = losses
            metrics.total_trades = total_pairs

        return metrics
