"""update_index 纯函数测试：新增、同键覆盖、倒序。"""
from finreport.update_index import add_entry, entry_from_payload


def _payload(code="300308", name="中际旭创", period="2026 中报",
             generated="2026-08-22", tone="good"):
    return {
        "meta": {"code": code, "name": name, "period_label": period,
                 "generated": generated, "disclaimer": "测试"},
        "summary": {"tone": tone, "text": "x", "links": []},
    }


def test_entry_from_payload():
    e = entry_from_payload(_payload(), file="300308_2026中报.json")
    assert e == {"code": "300308", "name": "中际旭创", "period_label": "2026 中报",
                 "generated": "2026-08-22", "tone": "good", "file": "300308_2026中报.json"}


def test_add_entry_new():
    index = []
    index = add_entry(index, _payload(), "a.json")
    assert len(index) == 1 and index[0]["code"] == "300308"


def test_add_entry_same_code_period_overwrites():
    index = [entry_from_payload(_payload(generated="2026-08-01", tone="warn"), "a.json")]
    index = add_entry(index, _payload(generated="2026-08-22", tone="bad"), "a.json")
    assert len(index) == 1
    assert index[0]["generated"] == "2026-08-22"
    assert index[0]["tone"] == "bad"


def test_add_entry_sorted_desc():
    index = []
    index = add_entry(index, _payload(code="000001", generated="2026-08-01"), "a.json")
    index = add_entry(index, _payload(code="300308", generated="2026-08-22"), "b.json")
    assert [e["code"] for e in index] == ["300308", "000001"]


def test_add_entry_no_summary_tone_warn():
    p = _payload()
    p.pop("summary")
    e = entry_from_payload(p, "a.json")
    assert e["tone"] == "warn"  # summary 缺失时默认 warn
