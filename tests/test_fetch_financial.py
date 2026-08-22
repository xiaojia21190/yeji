"""fetch_financial 冒烟：结构断言 + 已人工验证的锚点数字（300308 中际旭创 2026 中报）。"""
import subprocess
import sys
import json
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.net

ANCHOR = {  # 2026-06-30 报告期锚点（元）
    "归母净利润": 1.365115e10,
    "扣非净利润": 1.309160e10,
    "营业总收入": 4.177786e10,
}


def run_fetch(code: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from finreport.fetch_dev import fetch_abstract_dict; "
         "import json; print(json.dumps(fetch_abstract_dict('%s')))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_abstract_anchor_300308():
    data = run_fetch("300308")
    periods = data["periods"]
    assert "20260630" in periods and "20260331" in periods
    for metric, expected in ANCHOR.items():
        actual = data["series"][metric]["20260630"]
        assert actual == pytest.approx(expected, rel=2e-3), metric
