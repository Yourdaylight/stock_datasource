"""Timing schemas — 择时服务数据模型"""

from pydantic import BaseModel, Field


class RegimeResponse(BaseModel):
    """市场状态响应"""

    regime: str  # strong_bull / bull / consolidation / bear / strong_bear
    position_level: float  # 0.0 ~ 1.0
    confidence: float
    reason: str
    signal_date: str
    indicators: dict = {}


class SignalItem(BaseModel):
    """单条择时信号"""

    ts_code: str
    stock_name: str = ""
    action: str  # buy / sell / hold
    price: float
    confidence: float
    reason: str
    regime_adjusted: bool = True


class PipelineResult(BaseModel):
    """每日 pipeline 执行结果"""

    regime: RegimeResponse
    signals_generated: int = 0
    trades_executed: int = 0
    signals: list[SignalItem] = []
    errors: list[str] = []
    message: str = ""


class TimingHistoryItem(BaseModel):
    """历史 regime 记录"""

    date: str
    regime: str
    position_level: float
    close_price: float = 0.0


class RunPipelineRequest(BaseModel):
    """手动触发 pipeline"""

    account_id: str
    watchlist: list[str] = Field(
        default_factory=list,
        description="观察池股票列表，为空则使用当前持仓 + 默认列表",
    )
