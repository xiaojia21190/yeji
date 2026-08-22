"""quarter_math 纯函数测试。数字取自已验证的中际旭创 2026 中报真实数据。"""
import pytest
from finreport.quarter_math import (
    single_quarter, season_ratio, backcast, verdict, calc_market_cap,
    fmt_yi,
)


class TestSingleQuarter:
    def test_q2_from_h1_minus_q1(self):
        # H1 归母 136.5115 亿 - Q1 57.34502 亿 = 79.17 亿（参考报告 79.16，四舍五入差异）
        q2 = single_quarter(136.5115e8, 57.34502e8)
        assert q2 == pytest.approx(79.16648e8, rel=1e-4)

    def test_q4_from_annual(self):
        assert single_quarter(100e8, 25e8) == pytest.approx(75e8)


class TestSeasonRatio:
    def test_ratio_from_history(self):
        # 2025 全年 107.9725 亿，2025H1 39.95115 亿 → 37.0%
        r = season_ratio(h1_prior=39.95115e8, annual_prior=107.9725e8)
        assert r == pytest.approx(0.37003, rel=1e-3)

    def test_zero_annual_returns_none(self):
        assert season_ratio(h1_prior=1e8, annual_prior=0) is None


class TestBackcast:
    def test_backcast_q2(self):
        # 全年 340.7 亿 × 39.2% = 133.55 亿 H1，减 Q1 57.345 → 76.2 亿 Q2（参考报告交银 76.3）
        q2 = backcast(annual_forecast=340.7e8, ratio=0.392, q1_actual=57.345e8)
        assert q2 == pytest.approx(76.21e8, rel=1e-2)

    def test_backcast_needs_ratio(self):
        assert backcast(annual_forecast=340.7e8, ratio=None, q1_actual=57e8) is None


class TestVerdict:
    def test_meet_within_tolerance(self):
        # 实际 79.16，预期 79.4，差 -0.24%（容差内）→ 达标
        state, diff = verdict(actual=79.16e8, expected=79.4e8)
        assert state == "达标"
        assert diff == pytest.approx(-0.24e8, rel=1e-3)

    def test_miss_higher_than_tolerance(self):
        state, diff = verdict(actual=79.16e8, expected=93.2e8)
        assert state == "未达标"
        assert diff == pytest.approx(-14.04e8, rel=1e-3)

    def test_negative_actual(self):
        assert verdict(actual=-2e8, expected=1e8)[0] == "未达标"


class TestMarketCap:
    def test_total_cap(self):
        # 11.15234641 亿股 × 943 元 = 10516.7 亿
        cap = calc_market_cap(shares=1115234641, price=943.0)
        assert cap == pytest.approx(10516.66e8, rel=1e-4)


class TestFmtYi:
    def test_fmt(self):
        assert fmt_yi(13651150000.0) == "136.51"
        assert fmt_yi(None) == "—"
