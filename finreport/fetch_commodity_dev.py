"""商品期货主力连续取数：资源周期行业画像的核心跟踪变量（金价/铜价/油价等）。

新浪期货主力连续日线（futures_main_sina），脚本内算好区间涨跌幅与一年价格分位，
走势因素表可直接引用。skill 部署时 scripts/fetch_commodity.py 以薄 CLI 包装本模块。
"""
from __future__ import annotations

import datetime as dt

import akshare as ak

# 常用主力连续展示名；未收录品种原样输出 symbol
ALIASES = {
    "AU0": "沪金主力", "AG0": "沪银主力",
    "CU0": "沪铜主力", "AL0": "沪铝主力", "ZN0": "沪锌主力",
    "PB0": "沪铅主力", "NI0": "沪镍主力", "SN0": "沪锡主力",
    "RB0": "螺纹钢主力", "HC0": "热卷主力", "I0": "铁矿石主力",
    "SC0": "原油主力", "FU0": "燃油主力",
    "FG0": "玻璃主力", "SA0": "纯碱主力",
}


def _change(dates: list[dt.date], closes: list[float], days: int,
            last_date: dt.date) -> float | None:
    """近 N 日涨跌幅（小数）：基准 = last_date−days 当日或之前最近收盘。

    dates 升序；窗口内无基准日或基准非正时返回 None。
    """
    target = last_date - dt.timedelta(days=days)
    base = None
    for d, c in zip(dates, closes):
        if d <= target:
            base = c
        else:
            break
    if base is None or base <= 0:
        return None
    return closes[-1] / base - 1


def _ytd(dates: list[dt.date], closes: list[float],
         last_date: dt.date) -> float | None:
    """年初至今涨跌幅：基准 = 上一年度最后一个交易日收盘。窗口内无上年数据返回 None。"""
    base = None
    for d, c in zip(dates, closes):
        if d.year < last_date.year:
            base = c
        else:
            break
    if base is None or base <= 0:
        return None
    return closes[-1] / base - 1


def _range_pos(closes: list[float]) -> float | None:
    """一年价格分位（0~1）：当前收盘在回看窗口 [最低,最高] 区间的位置。极差为 0 返回 None。"""
    lo, hi = min(closes), max(closes)
    if hi <= lo:
        return None
    return (closes[-1] - lo) / (hi - lo)


def fetch_commodity(symbols: list[str], lookback_days: int = 450) -> dict:
    """{symbol: {name, last, date, chg_1m, chg_3m, chg_ytd, chg_1y, range_pos}}。

    单品种失败时对应 key 为 {"error": ...}，不阻塞其他品种。
    """
    out: dict = {}
    end = dt.date.today().strftime("%Y%m%d")
    start = (dt.date.today() - dt.timedelta(days=lookback_days)).strftime("%Y%m%d")
    for sym in symbols:
        try:
            df = ak.futures_main_sina(symbol=sym, start_date=start, end_date=end)
            if df is None or df.empty:
                raise ValueError("empty history")
            dates = [dt.date.fromisoformat(str(x)[:10]) for x in df["日期"]]
            closes = [float(x) for x in df["收盘价"]]
            last_date = dates[-1]
            out[sym] = {
                "name": ALIASES.get(sym, sym),
                "last": closes[-1],
                "date": last_date.isoformat(),
                "chg_1m": _change(dates, closes, 30, last_date),
                "chg_3m": _change(dates, closes, 91, last_date),
                "chg_ytd": _ytd(dates, closes, last_date),
                "chg_1y": _change(dates, closes, 365, last_date),
                "range_pos": _range_pos(closes),
            }
        except Exception as exc:
            out[sym] = {"error": str(exc)[:200]}
    return out
