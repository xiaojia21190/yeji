"""行情与股本取数：新浪实时行情 + 最新日线兜底 + 资产负债表实收资本（总股本）。

禁用东财 push2 系接口（本机代理环境间歇性拒连，见计划头部事实表）。
"""
from __future__ import annotations

import datetime as dt

import akshare as ak

from .http import get_with_fallback


def fetch_market(code: str, latest_period: str | None = None) -> dict:
    """返回 {price, date, total_shares, total_market_cap}。

    code: 6 位纯数字；latest_period: 报告期 YYYYMMDD，用于对齐实收资本行。
    """
    price, date = _realtime_price(code)
    if price is None:
        price, date = _daily_last_price(code)
    shares = _total_shares(code, latest_period)
    return {
        "price": price,
        "date": date,
        "total_shares": shares,
        "total_market_cap": shares * price if (shares and price) else None,
    }


def _prefix(code: str) -> str:
    return ("sh" if code.startswith(("6", "9", "5")) else
            "bj" if code.startswith(("4", "8")) else "sz") + code


def _realtime_price(code: str) -> tuple[float | None, str]:
    """新浪实时行情：hq.sinajs.cn，GBK，需 Referer。返回 (价格, YYYY-MM-DD)。"""
    resp = get_with_fallback(
        f"https://hq.sinajs.cn/list={_prefix(code)}",
        headers={"Referer": "https://finance.sina.com.cn"},
    )
    text = resp.content.decode("gbk", errors="replace")
    # 格式: var hq_str_sz300308="名称,今开,昨收,现价,...,日期,时间";
    parts = text.split('"')[1].split(",")
    try:
        price = float(parts[3])
    except (IndexError, ValueError):
        return None, ""
    date = parts[30] if len(parts) > 30 else ""
    return price, date


def _daily_last_price(code: str) -> tuple[float, str]:
    """新浪日线兜底：取最近 5 个自然日内最后一根收盘。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=5)
    df = ak.stock_zh_a_daily(
        symbol=_prefix(code),
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    last = df.iloc[-1]
    return float(last["close"]), str(last["date"])


def _total_shares(code: str, latest_period: str | None) -> float | None:
    """总股本 = 资产负债表最新一期「实收资本(或股本)」。

    该口径默认 1 元面值（元数即股数）。与 EPS 隐含股本（归母净利/基本EPS）偏差 >5%
    时按 EPS 隐含股本——面值≠1 的公司（如紫金矿业 0.1 元面值）实收资本元数≠股数。
    """
    prefix = _prefix(code)
    df = ak.stock_financial_report_sina(stock=prefix, symbol="资产负债表")
    row = None
    if latest_period:
        hit = df[df["报告日"] == latest_period]
        if not hit.empty:
            row = hit.iloc[0]
    if row is None:
        row = df.iloc[0]
    registered = None
    try:
        registered = float(row.get("实收资本(或股本)"))
    except (TypeError, ValueError):
        pass
    implied = _eps_implied_shares(code, latest_period)
    if implied and (registered is None or abs(registered - implied) / implied > 0.05):
        return implied
    return registered


def _eps_implied_shares(code: str, latest_period: str | None) -> float | None:
    """EPS 隐含总股本 = 报告期归母净利 / 基本每股收益（加权平均口径）。"""
    try:
        ab = ak.stock_financial_abstract(symbol=code)
    except Exception:
        return None
    period = latest_period
    if period not in set(ab.columns.astype(str)):
        numeric = [c for c in ab.columns if c not in ("选项", "指标") and str(c).isdigit()]
        period = max(numeric) if numeric else None
    if period is None:
        return None

    def _val(metric: str) -> float | None:
        rows = ab[ab["指标"] == metric]
        if rows.empty:
            return None
        try:
            return float(rows.iloc[0][period])
        except (TypeError, ValueError, KeyError):
            return None

    np_profit, eps = _val("归母净利润"), _val("基本每股收益")
    if not np_profit or not eps:
        return None
    return np_profit / eps
