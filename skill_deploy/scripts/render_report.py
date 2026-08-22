"""报告渲染 CLI：python render_report.py payload.json [--out report.html] [--open]

payload.json 结构见 references/report-template.html 与 SKILL.md 附录。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.render_dev import render_report  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "report-template.html"


def main() -> None:
    ap = argparse.ArgumentParser(description="财报分析 HTML 报告渲染")
    ap.add_argument("payload", help="payload JSON 路径")
    ap.add_argument("--out", default=None, help="输出 HTML 路径")
    ap.add_argument("--open", action="store_true", help="渲染后用默认浏览器打开")
    args = ap.parse_args()

    data = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    html = render_report(data, template_path=str(TEMPLATE))
    out = Path(args.out) if args.out else Path(args.payload).with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"written {out}")
    if args.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
