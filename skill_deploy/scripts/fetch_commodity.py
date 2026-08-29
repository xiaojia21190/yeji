"""商品期货主力取数 CLI：python fetch_commodity.py AU0 CU0 [--days 450] [--out data.json]

输出 JSON：{symbol: {name, last, date, chg_1m, chg_3m, chg_ytd, chg_1y, range_pos}}。
涨跌幅为小数；range_pos 为一年价格分位（0~1，周期位置信号）。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"  # finreport 库位置

sys.path.insert(0, LIB)

from finreport.fetch_commodity_dev import ALIASES, fetch_commodity  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="商品期货主力连续取数（资源周期画像）")
    ap.add_argument("symbols", nargs="+", help="主力连续代码，如 AU0 CU0 SC0（常用：%s）"
                    % " ".join(list(ALIASES)[:8]))
    ap.add_argument("--days", type=int, default=450, help="回看自然日数（默认 450）")
    ap.add_argument("--out", default=None, help="输出 JSON 路径，缺省打印 stdout")
    args = ap.parse_args()

    data = fetch_commodity(args.symbols, lookback_days=args.days)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
