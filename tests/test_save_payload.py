"""save_payload 测试：JSON 落盘 + index 更新（tmp_path 隔离）。"""
import json

from finreport.render_dev import save_payload


def _payload(code="600519", generated="2026-08-22"):
    return {
        "meta": {"code": code, "name": "贵州茅台", "period_label": "2026 中报",
                 "generated": generated, "disclaimer": "测试"},
        "summary": {"tone": "good", "text": "符合预期", "links": []},
        "cards": [], "sections": [],
    }


def test_save_payload_writes_json_and_index(tmp_path):
    out = save_payload(_payload(), reports_dir=str(tmp_path))
    data = json.loads((tmp_path / "600519_2026中报.json").read_text(encoding="utf-8"))
    assert data["meta"]["code"] == "600519"
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 1 and index[0]["file"] == "600519_2026中报.json"
    assert out["file"] == "600519_2026中报.json"


def test_save_payload_overwrites_same_report(tmp_path):
    save_payload(_payload(generated="2026-08-01"), reports_dir=str(tmp_path))
    save_payload(_payload(generated="2026-08-22"), reports_dir=str(tmp_path))
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 1 and index[0]["generated"] == "2026-08-22"
