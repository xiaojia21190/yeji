"""财报数据取数 CLI：python fetch_financial.py 300308 [--period 20260630] [--out data.json]

输出 JSON：{periods, series, balance: {total_shares, period}}。新浪源，单位元。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"  # finreport 库位置

sys.path.insert(0, LIB)

from finreport.fetch_dev import fetch_abstract_dict  # noqa: E402
from finreport.fetch_market_dev import _total_shares  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="财报数据取数（新浪源）")
    ap.add_argument("code", help="6 位股票代码，如 300308")
    ap.add_argument("--period", default=None, help="报告期 YYYYMMDD，用于对齐股本")
    ap.add_argument("--out", default=None, help="输出 JSON 路径，缺省打印 stdout")
    args = ap.parse_args()

    data = fetch_abstract_dict(args.code)
    try:
        data["balance"] = {"total_shares": _total_shares(args.code, args.period),
                           "period": args.period}
    except Exception as exc:  # 股本失败不阻塞主数据
        data["balance"] = {"total_shares": None, "period": args.period,
                           "error": str(exc)[:200]}
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
