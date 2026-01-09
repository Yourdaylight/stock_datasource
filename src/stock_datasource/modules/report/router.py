"""Report module router."""

from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class FinancialData(BaseModel):
    period: str
    revenue: float = None
    net_profit: float = None
    total_assets: float = None
    total_liab: float = None
    roe: float = None
    gross_margin: float = None


class FinancialRequest(BaseModel):
    code: str
    report_type: str = "income"
    periods: int = 8


class FinancialResponse(BaseModel):
    code: str
    name: str
    data: List[FinancialData]


class CompareRequest(BaseModel):
    codes: List[str]
    metrics: List[str]


@router.post("/financial", response_model=FinancialResponse)
async def get_financial(request: FinancialRequest):
    """Get financial statement data."""
    # Mock implementation
    return FinancialResponse(
        code=request.code,
        name="示例公司",
        data=[
            FinancialData(period="2024Q3", revenue=100000000000, net_profit=50000000000, roe=0.25, gross_margin=0.9),
            FinancialData(period="2024Q2", revenue=95000000000, net_profit=48000000000, roe=0.24, gross_margin=0.89),
            FinancialData(period="2024Q1", revenue=90000000000, net_profit=45000000000, roe=0.23, gross_margin=0.88),
        ]
    )


@router.post("/compare")
async def compare_financials(request: CompareRequest):
    """Compare financial data across stocks."""
    return {}
