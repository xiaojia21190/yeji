"""fetch_statements 测试：字段映射/降级离线测 + 300308 真实网络冒烟。"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

from finreport.fetch_statements_dev import _normalize, fetch_statements


class TestNormalizeOffline:
    def _df(self, rows: dict[str, list]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_alias_fallback(self):
        # 营业总收入缺行时降级取营业收入；固定资产净额缺行取固定资产净值
        df = self._df({
            "报告日": ["20260630", "20251231"],
            "营业收入": [100.0, 90.0],
            "固定资产净值": [10.0, 9.0],
            "归属于母公司所有者的净利润": [5.0, 4.0],
        })
        out = _normalize(df, {
            "营业总收入": ["营业总收入", "营业收入"],
            "固定资产净额": ["固定资产净额", "固定资产净值"],
            "归母净利润": ["归属于母公司所有者的净利润"],
        }, max_periods=10)
        assert out["20260630"] == {"营业总收入": 100.0, "固定资产净额": 10.0, "归母净利润": 5.0}
        assert "20251231" in out

    def test_max_periods_desc(self):
        df = self._df({
            "报告日": ["20240331", "20260630", "20251231", "20260331"],
            "净利润": [1.0, 4.0, 3.0, 2.0],
        })
        out = _normalize(df, {"净利润": ["净利润"]}, max_periods=2)
        assert list(out.keys()) == ["20260630", "20260331"]

    def test_nan_and_non_numeric_skipped(self):
        df = self._df({
            "报告日": ["20260630"],
            "净利润": [float("nan")],
            "营业收入": ["-"],
            "营业成本": [22.5],
        })
        out = _normalize(df, {"净利润": ["净利润"], "营业收入": ["营业收入"],
                              "营业成本": ["营业成本"]}, max_periods=5)
        assert out["20260630"] == {"营业成本": 22.5}

    def test_empty_df(self):
        assert _normalize(pd.DataFrame(), {"净利润": ["净利润"]}, 5) == {}


@pytest.mark.net
class TestFetchStatementsNet:
    def test_300308_anchors(self):
        out = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             "import sys; sys.path.insert(0, r'%s'); "
             "from finreport.fetch_statements_dev import fetch_statements; "
             "import json; print(json.dumps(fetch_statements('300308')))" % SKILL_DEV],
            capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        assert out.returncode == 0, out.stderr[-2000:]
        data = json.loads(out.stdout.strip().splitlines()[-1])
        # 锚点：2026 中报已人工核对的披露值（元）
        assert data["income"]["20260630"]["归母净利润"] == pytest.approx(1.365115e10, rel=2e-3)
        assert data["income"]["20260630"]["营业总收入"] == pytest.approx(4.177786e10, rel=2e-3)
        assert data["balance"]["20260630"]["归母净资产"] > 3.9e10
        assert data["cashflow"]["20260630"]["经营现金流净额"] > 0
        assert len(data["income"]) >= 8  # 近 10 期序列，同比与趋势够用
        # 主营构成近两期，产品分类下光模块主业占比 > 90%
        seg_dates = sorted(data["segments"].keys())
        assert len(seg_dates) == 2
        products = data["segments"][seg_dates[-1]]["按产品分类"]
        main = max(products, key=lambda x: x["revenue"])
        assert main["revenue_ratio"] > 0.9

    def test_segments_have_margin(self):
        data = fetch_statements("300308")
        latest = sorted(data["segments"].keys())[-1]
        for items in data["segments"][latest].values():
            for item in items:
                assert set(item) == {"name", "revenue", "revenue_ratio", "gross_margin"}
