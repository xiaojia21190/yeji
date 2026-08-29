"""fetch_commodity 测试：区间涨跌幅/价格分位离线测 + AU0 真实网络冒烟。"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

from finreport.fetch_commodity_dev import _change, _range_pos, _ytd, fetch_commodity


class TestChangeOffline:
    def _series(self):
        # 2026-08-28 为最后交易日；回看窗口内构造已知价格
        dates = [date(2025, 8, 28), date(2025, 11, 28), date(2026, 1, 2),
                 date(2026, 5, 30), date(2026, 7, 29), date(2026, 8, 28)]
        closes = [100.0, 120.0, 150.0, 90.0, 110.0, 121.0]
        return dates, closes, dates[-1]

    def test_change_1y_exact_base(self):
        dates, closes, last = self._series()
        # 365 天前基准 = 2025-08-28 的 100 → +21%
        assert _change(dates, closes, 365, last) == pytest.approx(0.21)

    def test_change_uses_latest_before_target(self):
        dates, closes, last = self._series()
        # 91 天前 target=2026-05-29 → 基准取 2026-05-30 之前最近收盘 150？不，
        # 2026-05-30 > target，故基准为 2026-01-02 的 150 → 121/150−1
        assert _change(dates, closes, 91, last) == pytest.approx(121.0 / 150.0 - 1)

    def test_change_insufficient_window(self):
        dates, closes, last = self._series()
        # target = 2026-08-23：基准取 2026-07-29 的 110 → +10%（基准取目标日前最近收盘）
        assert _change(dates, closes, 7, last) == pytest.approx(0.10, rel=1e-6)
        # target 早于窗口首日 → 无基准返回 None
        assert _change(dates, closes, 370, last) is None

    def test_change_non_positive_base(self):
        d = [date(2025, 1, 1), date(2025, 6, 1)]
        c = [0.0, 10.0]
        assert _change(d, c, 365, date(2025, 6, 1)) is None

    def test_ytd_prior_year_base(self):
        dates, closes, last = self._series()
        # 上年最后收盘 = 2025-11-28 的 120 → 121/120−1
        assert _ytd(dates, closes, last) == pytest.approx(121.0 / 120.0 - 1)

    def test_ytd_no_prior_year(self):
        d = [date(2026, 1, 4), date(2026, 3, 1)]
        c = [10.0, 11.0]
        assert _ytd(d, c, date(2026, 3, 1)) is None

    def test_range_pos(self):
        assert _range_pos([10.0, 12.0, 20.0]) == pytest.approx(1.0)   # 收在最高
        assert _range_pos([10.0, 20.0, 5.0]) == pytest.approx(0.0)    # 收在最低
        assert _range_pos([20.0, 10.0, 11.0]) == pytest.approx(0.1)   # 区间 [10,20] 内 1/10
        assert _range_pos([7.0, 7.0, 7.0]) is None  # 极差为 0


@pytest.mark.net
class TestCommodityNet:
    def test_au0_smoke(self):
        out = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             "import sys; sys.path.insert(0, r'%s'); "
             "from finreport.fetch_commodity_dev import fetch_commodity; "
             "import json; print(json.dumps(fetch_commodity(['AU0'])))" % SKILL_DEV],
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        assert out.returncode == 0, out.stderr[-2000:]
        data = json.loads(out.stdout.strip().splitlines()[-1])
        v = data["AU0"]
        assert "error" not in v
        assert v["name"] == "沪金主力"
        assert v["last"] > 0
        assert v["chg_1y"] is not None and v["chg_ytd"] is not None
        assert 0 <= v["range_pos"] <= 1
