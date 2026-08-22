"""行情与市值 CLI：python fetch_market.py 300308 [--period 20260630] [--out market.json]

输出 JSON：{price, date, total_shares, total_market_cap}。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.fetch_market_dev import fetch_market  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="行情与总市值取数")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--period", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = fetch_market(args.code, args.period)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
