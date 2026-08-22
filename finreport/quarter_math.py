"""财报对照核心算式：单季拆解、季节系数反推、达标判定、市值换算。

金额单位约定：函数入参/返回值一律为「元」（与 akshare 新浪源一致），
展示层用 fmt_yi 转亿元。
"""
from __future__ import annotations

# 达标判定的相对容差：|实际-预期|/预期 ≤ 2% 视为达标
TOLERANCE = 0.02


def single_quarter(cum_curr: float, cum_prev: float) -> float:
    """累计值拆单季：当期累计 - 上期累计。如 H1 - Q1 = Q2。"""
    return cum_curr - cum_prev


def season_ratio(h1_prior: float, annual_prior: float) -> float | None:
    """季节系数：上一年 H1 占全年比例。全年为 0/缺失时返回 None。"""
    if not annual_prior:
        return None
    return h1_prior / annual_prior


def backcast(annual_forecast: float, ratio: float | None, q1_actual: float) -> float | None:
    """反推单季：全年预测 × 季节系数 - Q1 实际。系数缺失时返回 None。"""
    if ratio is None or not annual_forecast:
        return None
    return annual_forecast * ratio - q1_actual


def verdict(actual: float, expected: float, tolerance: float = TOLERANCE) -> tuple[str, float]:
    """达标判定。返回 (状态, 差额=实际-预期)。

    容差内达标；超出容差时实际高于预期算达标（超预期），低于算未达标。
    """
    diff = actual - expected
    if expected == 0:
        return ("未达标", diff)
    if abs(diff) / abs(expected) <= tolerance:
        return ("达标", diff)
    state = "达标" if diff > 0 else "未达标"
    return (state, diff)


def calc_market_cap(shares: float, price: float) -> float:
    """总市值（元）= 总股本 × 现价。"""
    return shares * price


def fmt_yi(value: float | None, ndigits: int = 2) -> str:
    """元 → 亿元字符串，缺失返回 —。"""
    if value is None:
        return "—"
    return f"{value / 1e8:.{ndigits}f}"
