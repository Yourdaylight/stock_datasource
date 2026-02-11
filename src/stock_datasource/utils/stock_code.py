"""Unified stock code validation and normalization for A-share and HK markets."""

import re
from typing import Tuple, Optional


def validate_and_normalize_stock_code(
    ts_code: str, market: str = "auto"
) -> Tuple[bool, str, Optional[str]]:
    """Validate and normalize stock code for A-share or HK markets.

    Args:
        ts_code: Raw stock code input
        market: Market type - "cn" for A-share, "hk" for Hong Kong, "auto" for auto-detect

    Returns:
        Tuple of (is_valid, normalized_code, error_message)
    """
    if not ts_code:
        return False, "", "股票代码不能为空"

    ts_code = ts_code.strip().upper()

    # Auto-detect market from code format
    if market == "auto":
        if re.match(r'^\d{5}\.HK$', ts_code) or (
            re.match(r'^\d{1,5}$', ts_code) and len(ts_code) <= 5
        ):
            market = "hk"
        else:
            market = "cn"

    if market == "hk":
        return _validate_hk_code(ts_code)
    else:
        return _validate_cn_code(ts_code)


def _validate_cn_code(ts_code: str) -> Tuple[bool, str, Optional[str]]:
    """Validate and normalize A-share stock code."""
    # Already in valid format (e.g., 600519.SH)
    if re.match(r'^\d{6}\.(SH|SZ|BJ)$', ts_code):
        return True, ts_code, None

    # 6-digit code without suffix
    if len(ts_code) == 6 and ts_code.isdigit():
        if ts_code.startswith('6'):
            return True, f"{ts_code}.SH", None
        elif ts_code.startswith(('0', '3')):
            return True, f"{ts_code}.SZ", None
        elif ts_code.startswith(('4', '8')):
            return True, f"{ts_code}.BJ", None
        else:
            return False, ts_code, f"无法识别的股票代码前缀: {ts_code}"

    return False, ts_code, (
        f"无效的股票代码格式: {ts_code}。"
        "请使用6位数字代码(如600519)或完整代码(如600519.SH)"
    )


def _validate_hk_code(ts_code: str) -> Tuple[bool, str, Optional[str]]:
    """Validate and normalize HK stock code."""
    # Already valid: 00700.HK
    if re.match(r'^\d{5}\.HK$', ts_code):
        return True, ts_code, None

    # 5-digit code without suffix
    if re.match(r'^\d{5}$', ts_code):
        return True, f"{ts_code}.HK", None

    # 1-4 digit with leading zero implied (e.g., 700 -> 00700.HK)
    if re.match(r'^\d{1,4}$', ts_code):
        return True, f"{ts_code.zfill(5)}.HK", None

    return False, ts_code, (
        f"无效的港股代码格式: {ts_code}。"
        "请使用5位数字代码(如00700)或完整代码(如00700.HK)"
    )


def validate_cn_stock_code(ts_code: str) -> Tuple[bool, str, Optional[str]]:
    """Convenience function for A-share stock code validation."""
    return validate_and_normalize_stock_code(ts_code, market="cn")


def validate_hk_stock_code(ts_code: str) -> Tuple[bool, str, Optional[str]]:
    """Convenience function for HK stock code validation."""
    return validate_and_normalize_stock_code(ts_code, market="hk")


def normalize_stock_code_for_router(code: str, market: str = "cn") -> str:
    """Normalize stock code for FastAPI router usage. Raises HTTPException on invalid code.

    Args:
        code: Raw stock code
        market: "cn" or "hk"

    Returns:
        Normalized stock code

    Raises:
        HTTPException: if the code is invalid
    """
    from fastapi import HTTPException

    is_valid, normalized, error_msg = validate_and_normalize_stock_code(code, market=market)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    return normalized
