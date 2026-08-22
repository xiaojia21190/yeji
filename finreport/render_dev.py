"""HTML 报告渲染：数据 dict → 单文件 HTML（无外部依赖）。"""
from __future__ import annotations

from html import escape
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "report-template.html"


def render_report(data: dict, template_path: str | None = None) -> str:
    tpl = Path(template_path) if template_path else DEFAULT_TEMPLATE
    html = tpl.read_text(encoding="utf-8")
    meta = data["meta"]
    html = html.replace("{{TITLE}}", escape(f"{meta['name']} {meta['period_label']} 财报分析"))
    html = html.replace("{{META.code}}", escape(str(meta["code"])))
    html = html.replace("{{META.period_label}}", escape(str(meta["period_label"])))
    html = html.replace("{{META.name}}", escape(str(meta["name"])))
    html = html.replace("{{META.generated}}", escape(str(meta["generated"])))
    html = html.replace("{{META.disclaimer}}", escape(str(meta["disclaimer"])))
    html = html.replace("{{CARDS}}", _render_cards(data.get("cards", [])))
    html = html.replace("{{SECTIONS}}", _render_sections(data.get("sections", [])))
    html = html.replace("{{SUMMARY}}", _render_summary(data.get("summary")))
    return html


def _render_summary(summary: dict | None) -> str:
    """顶部 AI 总结横幅：总评段落 + 模块锚点导航。payload 无 summary 时输出空。"""
    if not summary:
        return ""
    tone = escape(str(summary.get("tone", "warn")))
    parts = [
        f'<div class="summary" data-tone="{tone}">',
        '<div class="summary-head">AI 总结</div>',
        f'<div class="summary-text">{escape(str(summary.get("text", "")))}</div>',
    ]
    links = summary.get("links") or []
    if links:
        anchors = " ".join(
            f'<a href="#{escape(str(l["id"]))}">{escape(str(l["label"]))}</a>'
            for l in links if l.get("id")
        )
        if anchors:
            parts.append(f'<div class="summary-links">{anchors}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def _render_cards(cards: list[dict]) -> str:
    parts = []
    for c in cards:
        tone = escape(str(c.get("tone", "warn")))
        parts.append(
            f'<div class="card" data-tone="{tone}">'
            f'<div class="label">{escape(str(c["label"]))}</div>'
            f'<div class="value">{escape(str(c["value"]))}</div>'
            f'<span class="tag {tone}">{escape(str(c.get("tag", "")))}</span></div>'
        )
    return "\n".join(parts)


def _render_sections(sections: list[dict]) -> str:
    parts = []
    for s in sections:
        body = [f'<section id="{escape(str(s.get("id", "")))}">',
                f'<h2>{escape(str(s["title"]))}</h2>']
        if s.get("intro"):
            body.append(f'<div class="intro">{escape(str(s["intro"]))}</div>')
        for table in s.get("tables", []):
            body.append(f'<div class="table-scroll">{_render_table(table)}</div>')
        if s.get("conclusion"):
            tone = escape(str(s["conclusion"].get("tone", "warn")))
            body.append(f'<div class="conclusion {tone}">'
                        f'{escape(str(s["conclusion"]["text"]))}</div>')
        for note in s.get("notes", []):
            body.append(f'<div class="note">{escape(str(note))}</div>')
        body.append("</section>")
        parts.append("\n".join(body))
    return "\n".join(parts)


def _render_table(table: dict) -> str:
    cols = "".join(f"<th>{escape(str(c))}</th>" for c in table["columns"])
    rows = []
    for i, row in enumerate(table["rows"]):
        tones = table.get("row_tones") or []
        cls = f' class="row-{escape(str(tones[i]))}"' if i < len(tones) and tones[i] else ""
        tds = "".join(f"<td>{escape(str(v))}</td>" for v in row)
        rows.append(f"<tr{cls}>{tds}</tr>")
    return f'<table><thead><tr>{cols}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
