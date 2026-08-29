"""定时扫描：watchlist 公司新财报披露检测。

检测逻辑：财务摘要接口的最新报告期 = 新披露期；reports/ 目录即状态——
{code}_{period_label}.json 已存在则视为已处理。接口失败的公司跳过并警告，不阻塞其他。
"""
from __future__ import annotations

from pathlib import Path

from .fetch_dev import fetch_abstract_dict

SEASON_LABEL = {"0331": "一季报", "0630": "中报", "0930": "三季报", "1231": "年报"}


def period_label(period: str) -> str:
    """'20260630' → '2026 中报'（payload 展示口径；文件名去空格）。"""
    return f"{period[:4]} {SEASON_LABEL[period[4:]]}"


def scan(watchlist: list[dict], reports_dir: str = "reports") -> list[dict]:
    """返回待生成快报的新披露列表 [{code, name, period, label}]。"""
    rd = Path(reports_dir)
    pending: list[dict] = []
    for item in watchlist:
        code, name = str(item["code"]), str(item.get("name", item["code"]))
        try:
            data = fetch_abstract_dict(code)
        except Exception as exc:
            print(f"[scan] {code} {name} 摘要取数失败，跳过：{str(exc)[:120]}")
            continue
        periods = [p for p in data.get("periods", []) if data["series"]]
        if not periods:
            continue
        period = periods[0]
        label = period_label(period)
        if (rd / f"{code}_{label.replace(' ', '')}.json").exists():
            continue
        pending.append({"code": code, "name": name, "period": period, "label": label,
                        "peers": list(item.get("peers", []))})
    return pending
