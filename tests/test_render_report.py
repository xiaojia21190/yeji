"""render_dev 渲染测试：用最小数据集断言 HTML 结构与关键内容。"""
from pathlib import Path

from finreport.render_dev import render_report

TPL = Path(__file__).resolve().parents[1] / "finreport" / "report-template.html"

MINIMAL = {
    "meta": {"code": "300308", "name": "中际旭创", "period_label": "2026 中报",
             "generated": "2026-08-22", "disclaimer": "仅列事实与数字，不构成任何投资建议。"},
    "cards": [
        {"label": "Q2 归母净利", "value": "79.16 亿", "tag": "符合预期", "tone": "good"},
        {"label": "Q2 扣非净利", "value": "73.73 亿", "tag": "不符合预期", "tone": "bad"},
    ],
    "sections": [
        {"title": "1 Q2 净利润（归母）是否符合预期",
         "intro": "归母净利 79.16 亿，对照各机构反推值",
         "tables": [{"columns": ["机构", "评级", "26E 全年净利", "反推 Q2", "差额", "判定"],
                     "rows": [["高盛", "买入", "384 亿", "93.2 亿", "-14.0 亿", "× 未达到"]],
                     "row_tones": ["bad"]}],
         "conclusion": {"text": "8 家机构中 4 家达标。", "tone": "good"},
         "notes": ["反推算式：全年 × 39.2% - Q1"]},
    ],
}


def test_render_contains_all_blocks():
    html = render_report(MINIMAL, template_path=str(TPL))
    for needle in ["300308", "中际旭创 2026 中报", "Q2 归母净利", "79.16 亿",
                   "高盛", "93.2 亿", "未达到", "39.2%", "不构成任何投资建议"]:
        assert needle in html, needle
    # 色调 class 落位
    assert "tag good" in html
    assert "tag bad" in html
    # 单文件无外部依赖
    assert "<script src" not in html and 'link rel="stylesheet"' not in html


def test_render_table_row_tones():
    html = render_report(MINIMAL, template_path=str(TPL))
    # tone 只作为 data-tone 样式钩子出现在卡片上，行内 tone 转成 row-* class
    assert 'class="row-bad"' in html
    assert html.count("<table") >= 1
    # data-tone 与 tag class 成对出现
    assert 'data-tone="bad"' in html and 'class="tag bad"' in html
