"""行情股本取数冒烟。锚点=2026-08-21 收盘 943.0、
2026-06-30 总股本（实收资本）1115234641。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.net


def run_fetch(code: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from finreport.fetch_market_dev import fetch_market; "
         "import json; print(json.dumps(fetch_market('%s'), ensure_ascii=False))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_market_anchors():
    data = run_fetch("300308")
    # 实时价锚点：中际旭创 943 元上下（允许近期波动 ±15%）
    assert 800 <= data["price"] <= 1100
    assert data["date"], "应含行情日期"
    # 总股本锚点：资产负债表实收资本（2026-06-30 = 1115234641，股本短期不变）
    assert data["total_shares"] == pytest.approx(1115234641, rel=1e-3)
    # 总市值 = 股本 × 现价
    assert data["total_market_cap"] == pytest.approx(
        data["total_shares"] * data["price"], rel=1e-6)
