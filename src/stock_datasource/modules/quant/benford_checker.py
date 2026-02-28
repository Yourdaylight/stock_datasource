"""Benford's Law first-digit checker for financial data.

Applies Benford's first-digit law (chi-square test) to revenue/profit figures.
Used as a soft screening condition (flag, not hard reject).
"""

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Benford's expected distribution for digits 1-9
BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
    5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046,
}


def extract_first_digit(value: float) -> Optional[int]:
    """Extract the first significant digit from a number."""
    if value == 0 or math.isnan(value) or math.isinf(value):
        return None
    abs_val = abs(value)
    digit = int(str(abs_val).lstrip("0").lstrip(".").lstrip("0")[:1])
    return digit if 1 <= digit <= 9 else None


def benford_chi_square(values: pd.Series) -> tuple[float, float, dict]:
    """Perform chi-square goodness-of-fit test for Benford's law.

    Args:
        values: Series of financial figures (revenue, profit, etc.)

    Returns:
        (chi2_statistic, p_value, digit_distribution)
    """
    # Extract first digits
    digits = values.dropna().apply(lambda x: extract_first_digit(float(x)))
    digits = digits.dropna().astype(int)

    if len(digits) < 30:
        return 0.0, 1.0, {}

    # Observed distribution
    total = len(digits)
    observed = {}
    for d in range(1, 10):
        observed[d] = (digits == d).sum()

    # Chi-square test
    chi2 = 0.0
    for d in range(1, 10):
        expected_count = BENFORD_EXPECTED[d] * total
        if expected_count > 0:
            chi2 += ((observed[d] - expected_count) ** 2) / expected_count

    # p-value from chi-square distribution (df=8)
    from scipy import stats as scipy_stats
    p_value = 1 - scipy_stats.chi2.cdf(chi2, df=8)

    distribution = {
        str(d): {
            "observed": int(observed[d]),
            "expected": round(BENFORD_EXPECTED[d] * total, 1),
            "observed_pct": round(observed[d] / total * 100, 1),
            "expected_pct": round(BENFORD_EXPECTED[d] * 100, 1),
        }
        for d in range(1, 10)
    }

    return chi2, p_value, distribution


def check_benford_for_stock(
    revenue_series: pd.Series,
    profit_series: pd.Series,
    threshold_p: float = 0.05,
) -> dict:
    """Check Benford's law for a stock's financial data.

    Returns dict with chi2, p_value, pass status, and distribution details.
    """
    combined = pd.concat([revenue_series, profit_series]).dropna()

    if len(combined) < 20:
        return {
            "pass": True,
            "chi2": 0.0,
            "p_value": 1.0,
            "distribution": {},
            "sample_size": len(combined),
            "reason": "样本量不足，跳过检验",
        }

    chi2, p_value, distribution = benford_chi_square(combined)

    return {
        "pass": p_value >= threshold_p,
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 4),
        "distribution": distribution,
        "sample_size": len(combined),
        "reason": "" if p_value >= threshold_p else f"首位数字分布异常(p={p_value:.4f}<{threshold_p})",
    }
