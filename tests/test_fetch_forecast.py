"""机构预测取数冒烟：东财研报列表。锚点=交银国际 2026-07-22 EPS 29.119（已人工验证）。"""
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
         "from finreport.fetch_forecast_dev import fetch_reports; "
         "import json; print(json.dumps(fetch_reports('%s'), ensure_ascii=False))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_reports_contain_jiaoyin_anchor():
    data = run_fetch("300308")
    reports = data["reports"]
    assert len(reports) >= 5
    jy = [r for r in reports if "交银" in r["org"]]
    assert jy, "应含交银国际研报"
    latest = jy[0]  # 按日期降序的第一条
    assert latest["eps_2026"] == pytest.approx(29.119, rel=1e-3)
    assert latest["rating"] == "买入"
