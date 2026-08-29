"""三大报表明细取数 CLI：python fetch_statements.py 300308 [--periods 10] [--out data.json]

输出 JSON：{income, balance, cashflow, segments}。三大报表单位元（近 periods 期）；
segments 为东财 F10 主营构成近两期（revenue 元，比例/毛利率为小数）。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"  # finreport 库位置

sys.path.insert(0, LIB)

from finreport.fetch_statements_dev import fetch_statements  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="三大报表明细 + 主营构成取数（完整业绩判断）")
    ap.add_argument("code", help="6 位股票代码，如 300308")
    ap.add_argument("--periods", type=int, default=10, help="三大报表保留期数（默认 10）")
    ap.add_argument("--out", default=None, help="输出 JSON 路径，缺省打印 stdout")
    args = ap.parse_args()

    data = fetch_statements(args.code, max_periods=args.periods)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
