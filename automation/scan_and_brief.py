"""定时扫描 + 自动快报 CLI：python scan_and_brief.py [--watchlist watchlist.json] ...

流程：扫描新披露 → 逐家构建快报（量化 + 可选 AI）→ save_payload 落盘 reports/ →
写出 scan_result.json 供 CI 通知步骤使用。git 提交/推送由 workflow 负责。
环境变量：AI_API_KEY / AI_BASE_URL / AI_MODEL（可选，缺失即纯量化模式）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

from finreport.ai_summary_dev import _config  # noqa: E402
from finreport.auto_brief_dev import build_brief  # noqa: E402
from finreport.render_dev import save_payload  # noqa: E402
from finreport.scan_dev import scan  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="财报披露扫描 + 自动快报")
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--force", default=None,
                    help="强制为指定代码生成快报（跳过已存在检查），测试用")
    ap.add_argument("--no-ai", action="store_true", help="禁用 AI，纯量化快报")
    args = ap.parse_args()

    watchlist = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    key, _, _ = _config()
    use_ai = bool(key) and not args.no_ai
    print(f"[scan] watchlist={len(watchlist)} 家，AI={'on(' + os_env_model() + ')' if use_ai else 'off'}")

    if args.force:
        item = next((w for w in watchlist if str(w["code"]) == args.force), None)
        if item is None:
            raise SystemExit(f"--force {args.force} 不在 watchlist 中")
        pending = [{"code": str(item["code"]), "name": str(item.get("name", item["code"])),
                    "peers": item.get("peers", [])}]
    else:
        pending = scan(watchlist, args.reports_dir)

    produced = []
    for item in pending:
        code, name = item["code"], item["name"]
        print(f"[brief] {code} {name} 生成中……")
        try:
            payload = build_brief(code, name, peers=item.get("peers"), use_ai=use_ai)
        except Exception as exc:
            print(f"[brief] {code} 失败：{type(exc).__name__} {str(exc)[:200]}")
            continue
        result = save_payload(payload, reports_dir=args.reports_dir)
        grade = payload["cards"][-1]["value"]
        tone = payload["summary"]["tone"]
        produced.append({"code": code, "name": name, "file": result["file"],
                         "period": payload["meta"]["period_label"],
                         "grade": grade, "tone": tone,
                         "summary": payload["summary"]["text"][:200]})
        print(f"[brief] {code} → reports/{result['file']} 评级 {grade} tone {tone}")

    out = {"generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
           "ai": use_ai, "briefs": produced}
    Path("finreport_work").mkdir(exist_ok=True)
    Path("finreport_work/scan_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[done] 新快报 {len(produced)} 份；结果已写 finreport_work/scan_result.json")


def os_env_model() -> str:
    import os
    return os.environ.get("AI_MODEL", "deepseek-v4-flash")


if __name__ == "__main__":
    main()
