"""perf_math 纯函数测试。数字取自已验证的中际旭创 300308 真实披露值（2026 中报）。"""
import pytest

from finreport.perf_math import (
    DIMENSIONS,
    VERDICT_LABEL,
    advance_liabilities,
    advance_ratio,
    capex_ratio,
    cash_coverage,
    fcf,
    four_expense_rate,
    gearing,
    goodwill_ratio,
    grade_from_tones,
    growth_gap,
    interest_bearing_debt,
    non_recurring_ratio,
    roe_ttm,
    ttm_metric,
    turnaround,
    yoy,
)


class TestYoy:
    def test_h1_yoy(self):
        # 2026H1 归母 136.5115 亿 vs 2025H1 39.95115 亿 → +241.7%
        r = yoy(136.5115e8, 39.95115e8)
        assert r == pytest.approx(2.41696, rel=1e-4)

    def test_none_on_missing_or_bad_base(self):
        assert yoy(100.0, None) is None
        assert yoy(None, 100.0) is None
        assert yoy(100.0, 0.0) is None
        assert yoy(100.0, -50.0) is None  # 负基数不造数，扭亏走 turnaround

    def test_turnaround(self):
        assert turnaround(30.0, -10.0) is True
        assert turnaround(-30.0, -10.0) is False
        assert turnaround(30.0, 10.0) is False


class TestGrowthGap:
    def test_profit_outpaces_revenue(self):
        assert growth_gap(0.30, 0.20) == pytest.approx(0.10)

    def test_none_when_either_missing(self):
        assert growth_gap(None, 0.20) is None
        assert growth_gap(0.30, None) is None


class TestTtm:
    def test_ttm_profit(self):
        # TTM 归母 = 2025 年报 107.9725 + 2026H1 136.5115 − 2025H1 39.95115 = 204.53285 亿
        v = ttm_metric(latest_cum=136.5115e8, annual_prior=107.9725e8,
                       cum_prior_same_period=39.95115e8)
        assert v == pytest.approx(204.53285e8, rel=1e-6)

    def test_ttm_missing_input(self):
        assert ttm_metric(None, 100.0, 10.0) is None

    def test_roe_ttm(self):
        # TTM 204.53285 亿 / 期末归母净资产 398.59 亿 ≈ 51.3%
        r = roe_ttm(204.53285e8, 398.59161655e8)
        assert r == pytest.approx(0.5132, rel=1e-3)


class TestQuality:
    def test_cash_coverage(self):
        # 300308 2026H1：经营现金流 17.9967 亿 / 归母 136.5115 亿 ≈ 0.13（真实含金量信号）
        r = cash_coverage(17.99674832e8, 136.5115e8)
        assert r == pytest.approx(0.1318, rel=1e-3)

    def test_cash_coverage_zero_profit(self):
        assert cash_coverage(10.0, 0.0) is None

    def test_fcf(self):
        # 17.9967 − 48.0216 = −30.02 亿（300308 2026H1 真实为负 FCF，capex 强度 2.67）
        assert fcf(17.99674832e8, 48.02161195e8) == pytest.approx(-30.02486363e8, rel=1e-4)

    def test_capex_ratio(self):
        r = capex_ratio(48.02161195e8, 17.99674832e8)
        assert r == pytest.approx(2.6683, rel=1e-3)

    def test_non_recurring_ratio(self):
        # 1 − 扣非 130.9160/归母 136.5115 ≈ 4.1%
        r = non_recurring_ratio(136.5115e8, 130.9160e8)
        assert r == pytest.approx(0.0410, rel=2e-2)


class TestExpenseAndHealth:
    def test_four_expense_rate(self):
        # 300308 2026H1 四费 = 1.579 + 7.666 + 11.530 + 5.622 亿 / 营收 417.779 亿 ≈ 6.32%
        r = four_expense_rate(1.57903349e8, 7.66600089e8, 11.53028871e8, 5.62247446e8,
                              417.77861795e8)
        assert r == pytest.approx(0.0632, rel=2e-2)

    def test_four_expense_missing_item_counts_as_zero(self):
        assert four_expense_rate(10.0, None, 5.0, None, 100.0) == pytest.approx(0.15)

    def test_interest_bearing_debt(self):
        # 300308 2026H1：短借 3.993 + 长借 4.869 亿（应付债券缺失按 0）
        v = interest_bearing_debt(3.99307920e8, 4.86933690e8, None)
        assert v == pytest.approx(8.86241610e8)

    def test_interest_bearing_debt_all_missing(self):
        assert interest_bearing_debt(None, None, None) is None

    def test_gearing(self):
        # 负债合计 248.7545 / 资产总计 689.4220 ≈ 36.1%
        r = gearing(248.75450362e8, 689.42203737e8)
        assert r == pytest.approx(0.3608, rel=1e-3)

    def test_goodwill_ratio(self):
        # 商誉 19.3888 / 归母净资产 398.5916 ≈ 4.9%
        r = goodwill_ratio(19.38875332e8, 398.59161655e8)
        assert r == pytest.approx(0.0486, rel=1e-2)


class TestAdvance:
    def test_advance_liabilities_merge(self):
        # 300308 2026H1：合同负债 0.2071 亿，预收款项缺失按 0
        assert advance_liabilities(0.20708562e8, None) == pytest.approx(0.20708562e8)

    def test_advance_liabilities_all_missing(self):
        assert advance_liabilities(None, None) is None

    def test_advance_ratio(self):
        # 0.2071 亿 / 417.7786 亿 ≈ 0.05%——to B 长账期行业天然小，仅作辅助
        r = advance_ratio(0.20708562e8, 417.77861795e8)
        assert r == pytest.approx(0.000496, rel=2e-2)

    def test_advance_ratio_needs_both(self):
        assert advance_ratio(None, 100.0) is None
        assert advance_ratio(10.0, 0.0) is None


class TestGrade:
    def test_mapping_table(self):
        assert VERDICT_LABEL == {"A": "业绩优秀", "B": "业绩良好", "C": "业绩承压", "D": "业绩恶化"}
        assert set(DIMENSIONS) == {"growth", "profitability", "quality", "health", "drivers"}

    def test_all_good_is_a(self):
        tones = {d: "good" for d in DIMENSIONS}
        assert grade_from_tones(tones) == "A"

    def test_sum_two_is_b(self):
        tones = {"growth": "good", "profitability": "good", "quality": "warn",
                 "health": "warn", "drivers": "warn"}
        assert grade_from_tones(tones) == "B"

    def test_all_warn_is_c(self):
        tones = {d: "warn" for d in DIMENSIONS}
        assert grade_from_tones(tones) == "C"

    def test_all_bad_is_d(self):
        tones = {d: "bad" for d in DIMENSIONS}
        assert grade_from_tones(tones) == "D"

    def test_growth_and_quality_bad_caps_at_c(self):
        # 其余三维 good（sum=+1 本应 B），但增长失速 + 含金量差 → 压到 C
        tones = {"growth": "bad", "profitability": "good", "quality": "bad",
                 "health": "good", "drivers": "good"}
        assert grade_from_tones(tones) == "C"

    def test_missing_dimensions_count_as_warn(self):
        assert grade_from_tones({}) == "C"

    def test_three_bad_is_d(self):
        tones = {"growth": "bad", "profitability": "bad", "quality": "bad",
                 "health": "warn", "drivers": "warn"}
        assert grade_from_tones(tones) == "D"
