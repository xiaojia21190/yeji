"""报告清单维护：payload → 清单条目，新增/覆盖/倒序。纯函数无 IO。"""
from __future__ import annotations


def entry_from_payload(payload: dict, file: str) -> dict:
    """payload → index 条目。summary 缺失时 tone 默认 warn。"""
    meta = payload["meta"]
    summary = payload.get("summary") or {}
    return {
        "code": str(meta["code"]),
        "name": str(meta["name"]),
        "period_label": str(meta["period_label"]),
        "generated": str(meta["generated"]),
        "tone": str(summary.get("tone", "warn")),
        "file": file,
    }


def add_entry(index: list[dict], payload: dict, file: str) -> list[dict]:
    """新增或覆盖（同 code+period_label 视为同一份报告），返回按生成日期倒序的新清单。"""
    entry = entry_from_payload(payload, file)
    key = (entry["code"], entry["period_label"])
    merged = [e for e in index if (e["code"], e["period_label"]) != key]
    merged.append(entry)
    merged.sort(key=lambda e: e["generated"], reverse=True)
    return merged
