"""机构研报预测取数：东财研报列表 → 标准化列表（EPS 口径，元）。"""
from __future__ import annotations

import akshare as ak


def fetch_reports(code: str) -> dict:
    """返回 {reports: [{org, rating, date, eps_2026, eps_2027, title, pdf_url}]}，按日期降序。"""
    df = ak.stock_research_report_em(symbol=code)
    reports = []
    for _, row in df.iterrows():
        reports.append({
            "org": str(row.get("机构", "")),
            "rating": str(row.get("东财评级", "")),
            "date": str(row.get("日期", "")),
            "eps_2026": _to_float(row.get("2026-盈利预测-收益")),
            "eps_2027": _to_float(row.get("2027-盈利预测-收益")),
            "title": str(row.get("报告名称", "")),
            "pdf_url": str(row.get("报告PDF链接", "")),
        })
    reports.sort(key=lambda r: r["date"], reverse=True)
    return {"reports": reports}


def _to_float(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN -> None
    except (TypeError, ValueError):
        return None
