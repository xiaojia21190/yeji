"""auto_brief 离线测试：报告期标签 + 评分卡数值规则 + 全市场扫描的纯函数部分。"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finreport.auto_brief_dev import (
    growth_tone, health_tone, profitability_tone, quality_tone,
)
from finreport.scan_dev import market_periods, period_label


class TestPeriodLabel:
    def test_all_seasons(self):
        assert period_label("20260630") == "2026 中报"
        assert period_label("20260331") == "2026 一季报"
        assert period_label("20251231") == "2025 年报"
        assert period_label("20250930") == "2025 三季报"


class TestGrowthTone:
    def test_good_volume_price_both_up(self):
        assert growth_tone(0.15, 0.20, turned=False) == "good"

    def test_warn_when_profit_lags(self):
        # 净利 +30% 但营收 +5%：营收未过线 → warn（价格驱动型高增的量化近似）
        assert growth_tone(0.05, 0.30, turned=False) == "warn"

    def test_bad_on_negative(self):
        assert growth_tone(-0.02, 0.10, turned=False) == "bad"
        assert growth_tone(0.10, -0.05, turned=False) == "bad"

    def test_turnaround_is_warn_not_bad(self):
        assert growth_tone(0.20, None, turned=True) == "warn"


class TestProfitabilityTone:
    def test_good(self):
        assert profitability_tone(0.30, 0.25, True, 0.12) == "good"

    def test_bad_on_low_roe(self):
        assert profitability_tone(0.30, 0.25, True, 0.03) == "bad"

    def test_bad_on_margin_below_median_and_falling(self):
        assert profitability_tone(0.20, 0.25, False, 0.12) == "bad"

    def test_warn_when_margin_up_but_roe_mid(self):
        assert profitability_tone(0.30, 0.25, True, 0.07) == "warn"


class TestQualityTone:
    def test_good(self):
        assert quality_tone(1.0, 0.05, []) == "good"

    def test_bad_on_low_cash_coverage(self):
        assert quality_tone(0.4, 0.05, []) == "bad"

    def test_bad_on_one_off_dominant(self):
        assert quality_tone(1.2, 0.60, []) == "bad"

    def test_bad_on_warnings(self):
        assert quality_tone(1.0, 0.05, ["应收较年初+50% 明显快于营收同比+10%"]) == "bad"

    def test_warn_mid(self):
        assert quality_tone(0.65, 0.30, []) == "warn"

    def test_loss_ignores_cov_and_nonrec(self):
        # 亏损期净现比/非经常占比口径失真，不参与打分
        assert quality_tone(-4.64, -0.03, [], loss=True) == "warn"
        assert quality_tone(-4.64, -0.03, ["应收预警"], loss=True) == "bad"
        # 不带 loss 标志时负净现比仍判 bad（盈利公司现金流弱）
        assert quality_tone(-4.64, -0.03, []) == "bad"


class TestMarketPeriods:
    def test_windows(self):
        # 披露窗口交叉期（1-4 月）查两个期；巨潮参数一季/三季不带「报」
        assert market_periods(dt.date(2026, 4, 15)) == ["2025年报", "2026一季"]
        assert market_periods(dt.date(2026, 8, 29)) == ["2026一季", "2026半年报"]
        assert market_periods(dt.date(2026, 10, 30)) == ["2026半年报", "2026三季"]
        assert market_periods(dt.date(2026, 12, 1)) == ["2026三季"]


class TestHealthTone:
    def test_good(self):
        assert health_tone(0.45, 0.9, 0.05) == "good"

    def test_bad_on_goodwill(self):
        assert health_tone(0.45, 0.9, 0.35) == "bad"

    def test_bad_on_debt_over_two_times_cash(self):
        assert health_tone(0.45, 2.5, 0.05) == "bad"

    def test_bad_on_high_gearing(self):
        assert health_tone(0.75, 0.9, 0.05) == "bad"

    def test_warn_mid(self):
        assert health_tone(0.50, 1.5, 0.20) == "warn"
