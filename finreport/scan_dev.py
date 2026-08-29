"""定时扫描：财报披露检测（全市场日历优先，watchlist 逐只为降级路径）。

全市场路径：巨潮「预约披露表」一次调用返回全部沪深京公司，按「实际披露日期」
筛出回看窗口内新披露的名单；确认融合进快报构建（新浪摘要没同步该期即跳过计数）。
watchlist 路径（日历失败时降级）：财务摘要最新期 = 新披露；reports/ 目录即状态。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import akshare as ak

from .fetch_dev import fetch_abstract_dict

SEASON_LABEL = {"0331": "一季报", "0630": "中报", "0930": "三季报", "1231": "年报"}
# 巨潮 period 参数后缀（注意：一季/三季不带「报」）→ 报告期 mmdd
CNINFO_SUFFIX = {"一季": "0331", "半年报": "0630", "三季": "0930", "年报": "1231"}


def period_label(period: str) -> str:
    """'20260630' → '2026 中报'（payload 展示口径；文件名去空格）。"""
    return f"{period[:4]} {SEASON_LABEL[period[4:]]}"


def market_periods(today: dt.date | None = None) -> list[str]:
    """当前应扫描的巨潮财报期（最多两个，覆盖披露窗口与交叉期；巨潮参数格式）。"""
    today = today or dt.date.today()
    y, m = today.year, today.month
    if m <= 4:
        return [f"{y - 1}年报", f"{y}一季"]
    if m <= 8:
        return [f"{y}一季", f"{y}半年报"]
    if m <= 10:
        return [f"{y}半年报", f"{y}三季"]
    return [f"{y}三季"]


def _norm_name(name: str) -> str:
    return str(name).strip().replace("\u3000", "")


def scan_full_market(watchlist: list[dict], reports_dir: str = "reports",
                     lookback_days: int = 3, confirm_cap: int = 300,
                     today: dt.date | None = None) -> dict:
    """巨潮日历全市场扫描。返回 {calendar_ok, periods, candidates, new, truncated}。

    new = [{code, name, period, label, watchlist}]，watchlist 优先排序；
    新浪是否已同步该期不在此确认，由 build_brief 报告期缺失时跳过计数。
    """
    today = today or dt.date.today()
    cutoff = (today - dt.timedelta(days=lookback_days)).isoformat()
    wl_codes = {str(w["code"]) for w in watchlist}
    wl_peers = {str(w["code"]): list(w.get("peers", [])) for w in watchlist}

    candidates: dict[tuple[str, str], dict] = {}
    calendar_ok = True
    periods_used: list[str] = []
    for per in market_periods(today):
        try:
            df = ak.stock_report_disclosure(market="沪深京", period=per)
            periods_used.append(per)
        except Exception as exc:
            print(f"[scan] 日历 {per} 拉取失败：{str(exc)[:120]}")
            calendar_ok = False
            continue
        if df is None or df.empty or "实际披露" not in df.columns:
            continue
        for _, r in df.iterrows():
            d = str(r["实际披露"])[:10]
            if d < cutoff or d == "NaT":
                continue
            code = str(r["股票代码"]).zfill(6)
            period = per[:4] + CNINFO_SUFFIX[per[4:]]
            candidates[(code, period)] = {
                "code": code, "name": _norm_name(r["股票简称"]),
                "period": period, "label": period_label(period), "disclosed": d,
            }

    cand_list = sorted(candidates.values(),
                       key=lambda x: (not x["code"] in wl_codes, x["disclosed"], x["code"]))
    truncated = len(cand_list) > confirm_cap
    cand_list = cand_list[:confirm_cap]

    rd = Path(reports_dir)
    new = []
    for c in cand_list:
        if (rd / f"{c['code']}_{c['label'].replace(' ', '')}.json").exists():
            continue
        c["watchlist"] = c["code"] in wl_codes
        c["peers"] = wl_peers.get(c["code"], [])
        new.append(c)
    new.sort(key=lambda x: not x["watchlist"])
    return {"calendar_ok": calendar_ok, "periods": periods_used,
            "candidates": len(candidates), "new": new, "truncated": truncated}


def scan(watchlist: list[dict], reports_dir: str = "reports") -> list[dict]:
    """降级路径：watchlist 逐只查摘要（日历接口不可用时）。"""
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
                        "peers": list(item.get("peers", [])), "watchlist": True})
    return pending
