"""开发期取数实现：财务摘要 → 标准化 dict。skill 部署时整体复制到 scripts/fetch_financial.py。"""
from __future__ import annotations

import akshare as ak

# 报告关心的指标（对应 stock_financial_abstract 的「指标」列，名称已实测核对）
WANTED = [
    "归母净利润", "扣非净利润", "营业总收入", "经营现金流量净额",
    "毛利率", "净资产收益率(ROE)", "基本每股收益",
]


def fetch_abstract_dict(code: str) -> dict:
    """返回 {periods: [...], series: {指标: {报告日: 值(元或比率)}}}。"""
    df = ak.stock_financial_abstract(symbol=code)
    period_cols = [c for c in df.columns if c not in ("选项", "指标") and c.isdigit()]
    series: dict[str, dict[str, float]] = {}
    for metric in WANTED:
        rows = df[df["指标"] == metric]
        if rows.empty:
            continue
        row = rows.iloc[0]
        values = {}
        for col in period_cols:
            v = row[col]
            if v is not None and v != "False" and v != "-" and str(v).strip() != "":
                try:
                    values[col] = float(v)
                except (TypeError, ValueError):
                    pass
        series[metric] = values
    return {"periods": sorted(period_cols, reverse=True), "series": series}
