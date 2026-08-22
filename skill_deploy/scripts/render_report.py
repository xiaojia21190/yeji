"""报告发布 CLI：python render_report.py payload.json [--out report.html] [--no-serve]

默认：payload 落盘到 D:\\code\\yeji\\reports\\ 并更新 index.json（viewer 报告中心），
自动确保本地 8765 HTTP 服务运行并打开 viewer。
--out 指定时：走旧静态导出路径，生成单文件 HTML。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.render_dev import render_report, save_payload  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "report-template.html"
REPORTS_DIR = Path(LIB) / "reports"
VIEWER_URL = "http://localhost:8765/viewer.html"


def ensure_server() -> bool:
    """8765 服务不在运行则在 D:\\code\\yeji 后台启动。返回是否可用。"""
    try:
        urllib.request.urlopen(VIEWER_URL, timeout=2)
        return True
    except Exception:
        pass
    subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765"],
        cwd=LIB,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(10):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(VIEWER_URL, timeout=2)
            return True
        except Exception:
            continue
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="财报分析报告发布（报告中心 / 静态导出）")
    ap.add_argument("payload", help="payload JSON 路径")
    ap.add_argument("--out", default=None, help="静态导出单文件 HTML 路径（不进报告中心）")
    ap.add_argument("--no-serve", action="store_true", help="落盘后不起服务不打开浏览器")
    args = ap.parse_args()

    data = json.loads(Path(args.payload).read_text(encoding="utf-8"))

    if args.out:
        html = render_report(data, template_path=str(TEMPLATE))
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"written {args.out}")
        return

    result = save_payload(data, reports_dir=str(REPORTS_DIR))
    print(f"published to reports/{result['file']} (viewer 报告中心)")
    if not args.no_serve:
        if ensure_server():
            webbrowser.open(VIEWER_URL)
            print(f"viewer ready: {VIEWER_URL}")
        else:
            print(f"服务启动失败，手动运行: cd {LIB} && python -m http.server 8765")


if __name__ == "__main__":
    main()
