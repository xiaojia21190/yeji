"""定时扫描 + 自动快报 CLI：python scan_and_brief.py [--watchlist watchlist.json] ...

流程（全市场模式）：巨潮披露日历 1 次调用 → 回看窗口内新披露名单 → watchlist 优先、
按单次上限逐家构建快报（watchlist 带 AI，其余纯量化控成本）→ save_payload 落盘
reports/ → scan_result.json 供 CI 通知。日历接口失败自动降级为 watchlist 逐只扫描。
git 提交/推送由 workflow 负责；AI 环境变量见 finreport/ai_summary_dev。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

from finreport.ai_summary_dev import _config  # noqa: E402
from finreport.auto_brief_dev import build_brief  # noqa: E402
from finreport.render_dev import save_payload  # noqa: E402
from finreport.scan_dev import scan, scan_full_market  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="财报披露扫描 + 自动快报（全市场）")
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--force", default=None,
                    help="强制为指定代码生成快报（跳过已存在检查），测试用")
    ap.add_argument("--max-briefs", type=int, default=40,
                    help="单次生成上限（watchlist 不受限），积压顺延下一轮")
    ap.add_argument("--lookback-days", type=int, default=3,
                    help="日历回看窗口（覆盖周末与停摆日）")
    ap.add_argument("--no-ai", action="store_true", help="禁用 AI，纯量化快报")
    args = ap.parse_args()

    watchlist = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    wl_codes = {str(w["code"]) for w in watchlist}
    key, _, _ = _config()
    ai_on = bool(key) and not args.no_ai
    print(f"[scan] 模式=全市场（watchlist {len(watchlist)} 家），AI={ai_on}")

    if args.force:
        item = next((w for w in watchlist if str(w["code"]) == args.force), None)
        if item is None:
            raise SystemExit(f"--force {args.force} 不在 watchlist 中")
        pending = [{"code": str(item["code"]), "name": str(item.get("name", item["code"])),
                    "peers": item.get("peers", []), "watchlist": True}]
        cal = None
    else:
        try:
            cal = scan_full_market(watchlist, args.reports_dir,
                                   lookback_days=args.lookback_days)
        except Exception as exc:
            print(f"[scan] 日历扫描整体失败，降级 watchlist 逐只：{str(exc)[:150]}")
            cal = None
        if cal:
            wl = [x for x in cal["new"] if x["watchlist"]]
            rest = [x for x in cal["new"] if not x["watchlist"]]
            pending = wl + rest[:max(0, args.max_briefs - len(wl))]
            backlog = len(cal["new"]) - len(pending)
            print(f"[scan] 日历 OK（{cal['periods']}）：新披露 {cal['candidates']} 家，"
                  f"待生成 {len(cal['new'])}（watchlist {len(wl)}），本次处理 {len(pending)}，"
                  f"积压 {backlog}")
        else:
            pending = scan(watchlist, args.reports_dir)
            backlog = 0
            print(f"[scan] 降级模式：watchlist 待生成 {len(pending)}")

    produced, skipped_sync = [], 0
    for item in pending:
        code, name = item["code"], item["name"]
        print(f"[brief] {code} {name}（{'watchlist' if item.get('watchlist') else '全市场'}"
              f"{'/AI' if ai_on else '/纯量化'}）生成中……")
        try:
            payload = build_brief(code, name, peers=item.get("peers"),
                                  use_ai=ai_on, period=item.get("period"))
        except ValueError as exc:
            skipped_sync += 1
            print(f"[brief] {code} 跳过：{exc}")
            continue
        except Exception as exc:
            print(f"[brief] {code} 失败：{type(exc).__name__} {str(exc)[:200]}")
            continue
        result = save_payload(payload, reports_dir=args.reports_dir)
        grade = payload["cards"][-1]["value"]
        produced.append({"code": code, "name": name, "file": result["file"],
                         "period": payload["meta"]["period_label"], "grade": grade,
                         "tone": payload["summary"]["tone"],
                         "watchlist": bool(item.get("watchlist")),
                         "summary": payload["summary"]["text"][:200]})
        print(f"[brief] {code} → reports/{result['file']} 评级 {grade}")

    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "ai": ai_on,
           "mode": "market" if cal else "watchlist",
           "market_candidates": cal["candidates"] if cal else None,
           "backlog": backlog if cal else 0, "skipped_sync": skipped_sync,
           "briefs": produced}
    Path("finreport_work").mkdir(exist_ok=True)
    Path("finreport_work/scan_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[done] 新快报 {len(produced)} 份（跳过未同步 {skipped_sync}）"
          f"；结果已写 finreport_work/scan_result.json")


if __name__ == "__main__":
    main()
