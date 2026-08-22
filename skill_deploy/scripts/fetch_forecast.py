"""机构预测取数 CLI：python fetch_forecast.py 300308 [--out forecast.json]

输出 JSON：{reports: [{org, rating, date, eps_2026, eps_2027, title, pdf_url}]}。
EPS 为元口径；净利 = EPS × 总股本 由分析阶段换算。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.fetch_forecast_dev import fetch_reports  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="机构研报预测取数（东财研报列表）")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = fetch_reports(args.code)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
