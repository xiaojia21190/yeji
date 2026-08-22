# 本地报告中心（viewer）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把逐次生成 HTML 改为固定 viewer.html 报告中心：报告以 payload JSON 存 `reports/`，viewer 列表点选查看，skill 渲染步骤自动落盘并起本地 HTTP 服务。

**Architecture:** 纯前端无框架——viewer.html 内置清单加载/搜索/渲染（现有暗色模板 CSS 与结构搬到 JS 渲染函数）；Python 侧新增 `update_index.py` 纯函数与 `render_dev.save_payload()`；skill 的 `render_report.py` 切换为调 `save_payload` 并保留 `--out` 静态导出老路径。CORS 用 `python -m http.server 8765` 解决，skill 自动检测并后台起服务。

**Tech Stack:** 原生 JS（fetch/DOM，无构建无依赖）+ Python 3.13 + pytest。无新增第三方依赖。

**关键既有事实：**

- payload 结构（已稳定）：`meta{code,name,period_label,generated,disclaimer}` + `summary{text,tone,links[{id,label}]}` + `cards[{label,value,tag,tone}]` + `sections[{id,title,intro,tables[{columns,rows,row_tones}],conclusion{tone,text}|null,notes[]}]`
- 现有两份 payload：`finreport_work/payload.json`（300308）、`finreport_work/my_payload.json`（002714）
- 暗色模板：`finreport/report-template.html`（占位符 `{{TITLE}}/{{META.*}}/{{SUMMARY}}/{{CARDS}}/{{SECTIONS}}`），CSS 与结构是 viewer 渲染函数的翻译来源
- `render_dev.py` 现有：`render_report(data, template_path)`、`_render_summary/_render_cards/_render_sections/_render_table`
- skill 脚本：`C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py`（CLI：payload 路径 → HTML），镜像在 `D:\code\yeji\skill_deploy\`
- HTML 转义：Python 侧 `html.escape`，JS 侧用等价 `escapeHtml`

---

## 文件结构总览

```
D:\code\yeji\
├── viewer.html                        ← Task 3（新）
├── reports\
│   ├── index.json                     ← Task 2 生成
│   ├── 300308_2026中报.json           ← Task 2 迁移
│   └── 002714_2026中报.json           ← Task 2 迁移
├── finreport\
│   ├── update_index.py                ← Task 1（新，纯函数）
│   └── render_dev.py                  ← Task 2 加 save_payload
├── tests\
│   ├── test_update_index.py           ← Task 1
│   └── test_save_payload.py           ← Task 2
└── skill 部署（Task 4 同步）
    C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py（改）
    C:\Users\35033\.claude\skills\fin-report\SKILL.md（改）
    D:\code\yeji\skill_deploy\（镜像同步）
```

---

### Task 1: update_index 纯函数（TDD）

**Files:**
- Create: `D:\code\yeji\finreport\update_index.py`
- Test: `D:\code\yeji\tests\test_update_index.py`

- [ ] **Step 1: 写失败测试**

`D:\code\yeji\tests\test_update_index.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_update_index.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 update_index.py**

`D:\code\yeji\finreport\update_index.py`：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_update_index.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 报告清单维护纯函数"
```

---

### Task 2: save_payload 落盘 + 迁移现有报告

**Files:**
- Modify: `D:\code\yeji\finreport\render_dev.py`（文件末尾追加 save_payload）
- Create: `D:\code\yeji\reports\`（300308/002714 JSON + index.json）
- Test: `D:\code\yeji\tests\test_save_payload.py`

- [ ] **Step 1: 写失败测试（tmp 目录，不打扰真实 reports/）**

`D:\code\yeji\tests\test_save_payload.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_save_payload.py -q`
Expected: FAIL（ImportError: save_payload）

- [ ] **Step 3: 在 render_dev.py 末尾追加 save_payload**

在 `D:\code\yeji\finreport\render_dev.py` 文件末尾追加（同时在文件头部 import 区补 `import json`、`from pathlib import Path` 已有则不重复；补 `from .update_index import add_entry`）：

```python
def save_payload(payload: dict, reports_dir: str = "reports") -> dict:
    """payload JSON 落盘到 reports_dir 并更新 index.json。

    文件名 {code}_{period_label}.json（period_label 去空格）。返回 {"file": 文件名}。
    """
    import json as _json  # 避免与文件头部可能的 import 冲突；直接局部导入

    rd = Path(reports_dir)
    rd.mkdir(parents=True, exist_ok=True)
    meta = payload["meta"]
    fname = f"{meta['code']}_{str(meta['period_label']).replace(' ', '')}.json"
    (rd / fname).write_text(_json.dumps(payload, ensure_ascii=False, indent=1),
                            encoding="utf-8")

    index_path = rd / "index.json"
    index = []
    if index_path.exists():
        try:
            index = _json.loads(index_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            index = []  # 损坏的 index 重建
    index = add_entry(index, payload, fname)
    index_path.write_text(_json.dumps(index, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return {"file": fname}
```

（若文件头部尚无 `from pathlib import Path` 则已有——render_dev.py 现有 DEFAULT_TEMPLATE 用到 Path，直接复用。）

- [ ] **Step 4: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_save_payload.py -v`
Expected: 2 passed

- [ ] **Step 5: 迁移现有两份报告**

```bash
cd D:/code/yeji && python -X utf8 -c "
import sys; sys.path.insert(0, '.')
import json
from pathlib import Path
from finreport.render_dev import save_payload
for src in ['finreport_work/payload.json', 'finreport_work/my_payload.json']:
    payload = json.loads(Path(src).read_text(encoding='utf-8'))
    print(save_payload(payload, reports_dir='reports'))
"
```

Expected: 输出 `{'file': '300308_2026中报.json'}` 与 `{'file': '002714_2026中报.json'}`；`reports/index.json` 两条目、300308 在前（generated 同为 2026-08-22 时 stable sort 保持插入序，002714 后插入应在前——按实现 sort 是 stable 的，同日期时后加入的在后面；此步验收只断言两条目齐全）。

验收命令：

```bash
cd D:/code/yeji && python -X utf8 -c "
import json
idx = json.load(open('reports/index.json', encoding='utf-8'))
assert {e['code'] for e in idx} == {'300308', '002714'}, idx
print('index OK:', [(e['code'], e['tone']) for e in idx])
"
```

Expected: `index OK: [('002714', 'bad'), ('300308', 'good')]` 或两条目顺序任一，code 集合正确即可。

- [ ] **Step 6: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: payload落盘与清单更新，迁移现有报告"
```

---

### Task 3: viewer.html 报告中心

**Files:**
- Create: `D:\code\yeji\viewer.html`

无 JS 测试框架（不引入 Node），验证方式：`python -m http.server` 冒烟 + 人眼验收。渲染函数从 `finreport/report-template.html` 与 `render_dev.py` 逐块翻译。

- [ ] **Step 1: 写 viewer.html**

`D:\code\yeji\viewer.html` 完整内容：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>财报分析报告中心</title>
<style>
  :root {
    --bg: #020617; --panel: #0F172A; --panel-2: #16213A;
    --ink: #F8FAFC; --sub: #94A3B8; --line: #1E293B;
    --good: #22C55E; --good-strong: #4ADE80; --good-bg: rgba(34,197,94,0.10);
    --bad: #FB7185; --bad-bg: rgba(251,113,133,0.10);
    --warn: #FBBF24; --warn-bg: rgba(251,191,36,0.10);
    --accent: #38BDF8; --accent-dim: rgba(56,189,248,0.14);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "IBM Plex Sans", "Segoe UI", "Microsoft YaHei", sans-serif;
    color: var(--ink); background: var(--bg); line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }
  .layout { display: flex; min-height: 100vh; }

  /* 侧栏 */
  .sidebar {
    width: 260px; flex-shrink: 0; background: var(--panel);
    border-right: 1px solid var(--line); padding: 16px 12px;
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
  }
  .sidebar h1 { font-size: 16px; margin-bottom: 4px; }
  .sidebar .sub { font-size: 12px; color: var(--sub); margin-bottom: 12px; }
  .search {
    width: 100%; padding: 8px 10px; border-radius: 8px; margin-bottom: 12px;
    background: var(--panel-2); border: 1px solid var(--line);
    color: var(--ink); font-size: 13px; outline: none;
  }
  .search:focus { border-color: var(--accent); }
  .report-list { display: flex; flex-direction: column; gap: 6px; }
  .report-item {
    padding: 10px 12px; border-radius: 8px; cursor: pointer;
    border: 1px solid transparent; transition: background-color 150ms ease;
  }
  .report-item:hover { background: var(--panel-2); }
  .report-item.active { background: var(--accent-dim); border-color: rgba(56,189,248,0.3); }
  .report-item .row1 { display: flex; align-items: center; gap: 8px; }
  .report-item .name { font-size: 14px; font-weight: 600; flex: 1; }
  .report-item .code { font-size: 11px; color: var(--accent); font-variant-numeric: tabular-nums; }
  .report-item .row2 { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
  .report-item .period { font-size: 12px; color: var(--sub); }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .dot.good { background: var(--good); } .dot.bad { background: var(--bad); } .dot.warn { background: var(--warn); }
  .report-item .date { font-size: 11px; color: var(--sub); margin-left: auto; }
  .report-item.broken .name { color: var(--bad); }

  /* 主区 */
  .main { flex: 1; min-width: 0; padding: 24px 28px 48px; }
  .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; }
  .btn {
    font-size: 13px; color: var(--accent); background: var(--accent-dim);
    border: 1px solid rgba(56,189,248,0.25); border-radius: 8px;
    padding: 6px 14px; cursor: pointer; transition: background-color 200ms ease;
  }
  .btn:hover { background: rgba(56,189,248,0.22); }
  .hint {
    background: var(--warn-bg); border: 1px solid rgba(251,191,36,0.3);
    color: var(--warn); border-radius: 8px; padding: 10px 14px;
    font-size: 13px; margin-bottom: 14px; display: none;
  }
  .hint code { background: rgba(0,0,0,0.3); padding: 1px 6px; border-radius: 4px; font-size: 12px; }

  .empty { color: var(--sub); text-align: center; padding: 80px 20px; font-size: 14px; }

  /* ===== 报告样式（自 report-template.html 原样翻译） ===== */
  .report { max-width: 980px; }
  .report header { border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 16px; }
  .crumb { color: var(--sub); font-size: 13px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .code-badge {
    color: var(--accent); background: var(--accent-dim); font-variant-numeric: tabular-nums;
    border: 1px solid rgba(56,189,248,0.25); border-radius: 6px; padding: 1px 8px; font-weight: 600;
  }
  .report h1.report-title { font-size: 24px; font-weight: 700; margin: 10px 0 4px; }
  .report h1 .period { color: var(--accent); }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .chip { font-size: 12px; color: #CBD5E1; border: 1px solid var(--line); background: var(--panel); border-radius: 999px; padding: 3px 12px; }

  .summary {
    background: linear-gradient(135deg, var(--panel-2) 0%, var(--panel) 100%);
    border: 1px solid var(--line); border-left: 3px solid var(--sum-tone, var(--accent));
    border-radius: 12px; padding: 18px 20px; margin: 18px 0 8px;
  }
  .summary[data-tone="good"] { --sum-tone: var(--good); }
  .summary[data-tone="bad"] { --sum-tone: var(--bad); }
  .summary[data-tone="warn"] { --sum-tone: var(--warn); }
  .summary .summary-head { font-size: 13px; font-weight: 600; color: var(--sub); letter-spacing: 0.08em; margin-bottom: 8px; }
  .summary .summary-text { font-size: 14.5px; line-height: 1.8; }
  .summary .summary-links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }
  .summary .summary-links a { font-size: 12.5px; color: var(--accent); background: var(--accent-dim); border: 1px solid rgba(56,189,248,0.25); border-radius: 999px; padding: 3px 12px; text-decoration: none; }
  .summary .summary-links a:hover { background: rgba(56,189,248,0.22); }

  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 12px; margin: 16px 0 8px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px; position: relative; overflow: hidden; border-left-width: 1px; }
  .card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--card-tone, var(--line)); }
  .card[data-tone="good"] { --card-tone: var(--good); }
  .card[data-tone="bad"] { --card-tone: var(--bad); }
  .card[data-tone="warn"] { --card-tone: var(--warn); }
  .card .label { font-size: 12.5px; color: var(--sub); font-weight: 500; }
  .card .value { font-size: 22px; font-weight: 700; margin: 6px 0 8px; font-variant-numeric: tabular-nums; }
  .tag { display: inline-block; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 2px 9px; }
  .tag.good { color: var(--good-strong); background: var(--good-bg); border: 1px solid rgba(34,197,94,0.25); }
  .tag.bad { color: var(--bad); background: var(--bad-bg); border: 1px solid rgba(251,113,133,0.25); }
  .tag.warn { color: var(--warn); background: var(--warn-bg); border: 1px solid rgba(251,191,36,0.25); }

  section.rpt { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px 22px; margin: 16px 0; scroll-margin-top: 16px; }
  section.rpt h2 { font-size: 17px; font-weight: 700; margin-bottom: 10px; padding-left: 10px; border-left: 3px solid var(--accent); line-height: 1.4; }
  section.rpt .intro { color: var(--sub); font-size: 13.5px; margin-bottom: 12px; }
  .table-scroll { overflow-x: auto; border-radius: 8px; border: 1px solid var(--line); }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin: 8px 0; }
  th { text-align: left; color: var(--sub); font-weight: 600; background: var(--panel-2); border-bottom: 1px solid var(--line); padding: 8px 12px; white-space: nowrap; font-size: 12.5px; }
  td { border-bottom: 1px solid rgba(30,41,59,0.6); padding: 8px 12px; font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: rgba(56,189,248,0.05); }
  tr.row-good td { background: var(--good-bg); }
  tr.row-bad td { background: var(--bad-bg); }
  tr.row-warn td { background: var(--warn-bg); }
  .conclusion { border-radius: 8px; padding: 12px 14px; font-size: 14px; margin-top: 10px; border: 1px solid transparent; line-height: 1.7; }
  .conclusion.good { background: var(--good-bg); color: var(--good-strong); border-color: rgba(34,197,94,0.25); }
  .conclusion.bad { background: var(--bad-bg); color: var(--bad); border-color: rgba(251,113,133,0.25); }
  .conclusion.warn { background: var(--warn-bg); color: var(--warn); border-color: rgba(251,191,36,0.25); }
  .note { color: var(--sub); font-size: 12.5px; margin-top: 8px; padding-left: 12px; border-left: 2px solid var(--line); line-height: 1.7; }
  footer.rpt-footer { color: var(--sub); font-size: 12px; border-top: 1px solid var(--line); margin-top: 24px; padding-top: 12px; line-height: 1.8; }
  a { color: var(--accent); }
</style>
</head>
<body>
<div class="hint" id="cors-hint">
  直接打开的本地文件无法读取报告数据。请在 <b>D:\code\yeji</b> 目录运行
  <code>python -m http.server 8765</code>，然后访问
  <code>http://localhost:8765/viewer.html</code>
</div>
<div class="layout">
  <aside class="sidebar">
    <h1>财报分析报告中心</h1>
    <div class="sub">fin-report · 本地报告</div>
    <input class="search" id="search" type="search" placeholder="搜索代码 / 名称 / 报告期" aria-label="搜索报告">
    <div class="report-list" id="report-list"></div>
  </aside>
  <main class="main">
    <div class="toolbar">
      <button class="btn" id="btn-export" title="把当前报告导出为可分享的单文件 HTML">导出单文件 HTML</button>
    </div>
    <div id="report-area"><div class="empty">加载中…</div></div>
  </main>
</div>
<script>
"use strict";

// ===== 工具 =====
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ===== 渲染函数（自 render_dev.py 逐块翻译） =====
function renderReport(p) {
  const meta = p.meta;
  const parts = [];
  parts.push(`
    <div class="report">
      <header>
        <div class="crumb"><span class="code-badge">${escapeHtml(meta.code)}</span>
          <span>${escapeHtml(meta.period_label)}</span><span>·</span><span>业绩符合预期情况</span></div>
        <h1 class="report-title">${escapeHtml(meta.name)} <span class="period">${escapeHtml(meta.period_label)}</span> 财报分析</h1>
        <div class="chips">
          <span class="chip">只列事实与数字</span><span class="chip">机构预测逐家溯源</span>
          <span class="chip">反推算式可查</span><span class="chip">已剔除无原文依据机构</span>
        </div>
      </header>
      ${renderSummary(p.summary)}
      <div class="cards">${renderCards(p.cards || [])}</div>
      ${renderSections(p.sections || [])}
      <footer class="rpt-footer">生成于 ${escapeHtml(meta.generated)} · ${escapeHtml(meta.disclaimer)}</footer>
    </div>`);
  return parts.join("");
}

function renderSummary(s) {
  if (!s) return "";
  const tone = escapeHtml(s.tone || "warn");
  let links = "";
  if (Array.isArray(s.links) && s.links.length) {
    const anchors = s.links.filter(l => l && l.id)
      .map(l => `<a href="#${escapeHtml(l.id)}">${escapeHtml(l.label)}</a>`).join(" ");
    if (anchors) links = `<div class="summary-links">${anchors}</div>`;
  }
  return `<div class="summary" data-tone="${tone}">
    <div class="summary-head">AI 总结</div>
    <div class="summary-text">${escapeHtml(s.text || "")}</div>${links}</div>`;
}

function renderCards(cards) {
  return cards.map(c => {
    const tone = escapeHtml(c.tone || "warn");
    return `<div class="card" data-tone="${tone}">
      <div class="label">${escapeHtml(c.label)}</div>
      <div class="value">${escapeHtml(c.value)}</div>
      <span class="tag ${tone}">${escapeHtml(c.tag || "")}</span></div>`;
  }).join("\n");
}

function renderSections(sections) {
  return sections.map(s => {
    const body = [`<section class="rpt" id="${escapeHtml(s.id || "")}">
      <h2>${escapeHtml(s.title)}</h2>`];
    if (s.intro) body.push(`<div class="intro">${escapeHtml(s.intro)}</div>`);
    (s.tables || []).forEach(t => body.push(
      `<div class="table-scroll">${renderTable(t)}</div>`));
    if (s.conclusion) {
      const tone = escapeHtml(s.conclusion.tone || "warn");
      body.push(`<div class="conclusion ${tone}">${escapeHtml(s.conclusion.text)}</div>`);
    }
    (s.notes || []).forEach(n => body.push(`<div class="note">${escapeHtml(n)}</div>`));
    body.push("</section>");
    return body.join("\n");
  }).join("\n");
}

function renderTable(t) {
  const cols = t.columns.map(c => `<th>${escapeHtml(c)}</th>`).join("");
  const tones = t.row_tones || [];
  const rows = t.rows.map((r, i) => {
    const tone = tones[i];
    const cls = tone ? ` class="row-${escapeHtml(tone)}"` : "";
    return `<tr${cls}>${r.map(v => `<td>${escapeHtml(v)}</td>`).join("")}</tr>`;
  }).join("");
  return `<table><thead><tr>${cols}</tr></thead><tbody>${rows}</tbody></table>`;
}

// ===== 应用状态与交互 =====
const state = { index: [], current: null };

async function loadIndex() {
  const resp = await fetch("reports/index.json");
  if (!resp.ok) throw new Error("index " + resp.status);
  state.index = await resp.json();
}

function renderList(filter) {
  const list = document.getElementById("report-list");
  const kw = (filter || "").trim().toLowerCase();
  const items = state.index.filter(e =>
    !kw || [e.code, e.name, e.period_label].join(" ").toLowerCase().includes(kw));
  if (!items.length) {
    list.innerHTML = `<div class="empty" style="padding:30px 6px;font-size:13px;">${state.index.length ? "无匹配报告" : "暂无报告，运行 /fin-report 生成第一份"}</div>`;
    return;
  }
  list.innerHTML = items.map(e => `
    <div class="report-item${state.current === e.file ? " active" : ""}${e.broken ? " broken" : ""}" data-file="${escapeHtml(e.file)}" role="button" tabindex="0">
      <div class="row1"><span class="name">${escapeHtml(e.name)}</span><span class="code">${escapeHtml(e.code)}</span></div>
      <div class="row2"><span class="dot ${escapeHtml(e.tone)}"></span><span class="period">${escapeHtml(e.period_label)}</span><span class="date">${escapeHtml(e.generated)}</span></div>
    </div>`).join("");
  list.querySelectorAll(".report-item").forEach(el => {
    const open = () => openReport(el.dataset.file);
    el.addEventListener("click", open);
    el.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } });
  });
}

async function openReport(file) {
  state.current = file;
  renderList(document.getElementById("search").value);
  const area = document.getElementById("report-area");
  area.innerHTML = `<div class="empty">加载中…</div>`;
  try {
    const resp = await fetch("reports/" + encodeURIComponent(file));
    if (!resp.ok) throw new Error(resp.status);
    const payload = await resp.json();
    area.innerHTML = renderReport(payload);
    area.querySelectorAll('.summary-links a[href^="#"]').forEach(a => {
      a.addEventListener("click", ev => {
        const target = document.getElementById(a.getAttribute("href").slice(1));
        if (target) { ev.preventDefault(); target.scrollIntoView({behavior: "smooth"}); }
      });
    });
  } catch (err) {
    const entry = state.index.find(e => e.file === file);
    if (entry) entry.broken = true;
    area.innerHTML = `<div class="empty">报告加载失败（${escapeHtml(String(err))}）</div>`;
    renderList(document.getElementById("search").value);
  }
}

function exportHtml() {
  if (!state.current) { alert("请先选择一份报告"); return; }
  const reportNode = document.querySelector(".report");
  if (!reportNode) { alert("当前无可导出的报告内容"); return; }
  const doc = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>${escapeHtml(state.current)}</title>
<style>${document.querySelector("style").textContent}</style></head>
<body><div class="main">${reportNode.outerHTML}</div></body></html>`;
  const blob = new Blob([doc], { type: "text/html" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = state.current.replace(/\.json$/, "") + "_导出.html";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function main() {
  document.getElementById("search").addEventListener("input", e => renderList(e.target.value));
  document.getElementById("btn-export").addEventListener("click", exportHtml);
  try {
    await loadIndex();
  } catch (err) {
    document.getElementById("cors-hint").style.display = "block";
    document.getElementById("report-area").innerHTML =
      `<div class="empty">无法读取 reports/index.json<br><br>${escapeHtml(String(err))}</div>`;
    renderList("");
    return;
  }
  renderList("");
  if (state.index.length) await openReport(state.index[0].file);
}

main();
</script>
</body>
</html>
```

- [ ] **Step 2: 起 http.server 冒烟验证**

```bash
cd D:/code/yeji && (python -m http.server 8765 >/dev/null 2>&1 &) && sleep 2 && python -X utf8 -c "
import requests
# viewer 页面可达且结构正确
r = requests.get('http://localhost:8765/viewer.html', timeout=10)
assert r.status_code == 200 and '报告中心' in r.text
# index 与两份报告 JSON 可达
idx = requests.get('http://localhost:8765/reports/index.json', timeout=10).json()
assert {e['code'] for e in idx} >= {'300308', '002714'}
for e in idx:
    rr = requests.get('http://localhost:8765/reports/' + e['file'], timeout=10)
    assert rr.status_code == 200, e['file']
print('viewer smoke OK:', len(idx), '份报告')
"
```

Expected: `viewer smoke OK: 2 份报告`

- [ ] **Step 3: 人眼验收**

```bash
start "" "http://localhost:8765/viewer.html"
```

核对：左侧两家公司（牧原 bad 粉点在前或按日期序）、点选切换、搜索「牧原」过滤、导出按钮下载 HTML 可打开、报告区 summary/卡片/表格/结论色块与旧静态版一致。

- [ ] **Step 4: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 本地报告中心viewer"
```

---

### Task 4: skill 渲染链切换 + SKILL.md 更新 + 镜像同步

**Files:**
- Modify: `C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py`
- Modify: `C:\Users\35033\.claude\skills\fin-report\SKILL.md`
- Modify: `D:\code\yeji\skill_deploy\`（镜像同步）

- [ ] **Step 1: 改 skill render_report.py**

`C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py` 全文替换为：

```python
"""报告发布 CLI：python render_report.py payload.json [--out report.html] [--no-serve]

默认：payload 落盘到 D:\\code\\yeji\\reports\\ 并更新 index.json（viewer 报告中心），
自动确保本地 8765 HTTP 服务运行并打开 viewer。
--out 指定时：走旧静态导出路径，生成单文件 HTML。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.render_dev import render_report, save_payload  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "report-template.html"
REPORTS_DIR = Path(LIB) / "reports"
VIEWER_URL = "http://localhost:8765/viewer.html"


def ensure_server() -> bool:
    """8765 服务不在运行则在 D:\\code\\yeji 后台启动。返回是否可用。"""
    try:
        urllib.request.urlopen("http://localhost:8765/viewer.html", timeout=2)
        return True
    except Exception:
        pass
    subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765"],
        cwd=LIB,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(10):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(VIEWER_URL, timeout=2)
            return True
        except Exception:
            continue
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="财报分析报告发布（报告中心 / 静态导出）")
    ap.add_argument("payload", help="payload JSON 路径")
    ap.add_argument("--out", default=None, help="静态导出单文件 HTML 路径（不进报告中心）")
    ap.add_argument("--no-serve", action="store_true", help="落盘后不起服务不打开浏览器")
    args = ap.parse_args()

    data = json.loads(Path(args.payload).read_text(encoding="utf-8"))

    if args.out:
        html = render_report(data, template_path=str(TEMPLATE))
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"written {args.out}")
        return

    result = save_payload(data, reports_dir=str(REPORTS_DIR))
    print(f"published to reports/{result['file']} (viewer 报告中心)")
    if not args.no_serve:
        if ensure_server():
            webbrowser.open(VIEWER_URL)
            print(f"viewer ready: {VIEWER_URL}")
        else:
            print(f"服务启动失败，手动运行: cd {LIB} && python -m http.server 8765")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 skill 新链路（--no-serve 模式）**

```bash
cd D:/code/yeji && python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json --no-serve
```

Expected: `published to reports/300308_2026中报.json (viewer 报告中心)`；`reports/index.json` 中 300308 条目 generated 仍为 2026-08-22（覆盖不重复）。

验收：

```bash
cd D:/code/yeji && python -X utf8 -c "
import json
idx = json.load(open('reports/index.json', encoding='utf-8'))
codes = [e['code'] for e in idx]
assert codes.count('300308') == 1, codes
print('index 去重 OK:', codes)
"
```

- [ ] **Step 3: 更新 SKILL.md 渲染步骤（第 4 节整体替换）**

将 `C:\Users\35033\.claude\skills\fin-report\SKILL.md` 中「### 4. 渲染（脚本）」一节替换为：

```markdown
### 4. 发布（脚本）

payload 结构：meta{code,name,period_label,generated,disclaimer} + summary{text,tone,links[{id,label}]} + cards[] + sections[]{title,intro,tables[],conclusion{tone,text},notes[]}。
tone: good/bad/warn；表格 rows 与 row_tones 等长对齐。

**summary（顶部 AI 总结横幅，必填）**：3~5 句总评——四模块各一句 + 整体判断；tone 取四模块中最差与最好综合（整体偏差 bad / 喜忧参半 warn / 全面达标 good）；links 列出全部模块的 {id: section id, label: 模块简称}，点击跳转。summary 由分析阶段 AI 撰写，不写死模板。

发布到本地报告中心（默认，不再生成散装 HTML）：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json
```

脚本会把 JSON 落盘到 `D:\code\yeji\reports\`、更新 index.json、自动起 8765 服务并打开 `http://localhost:8765/viewer.html`（列表点选查看，支持搜索与导出单文件 HTML）。

需要单发一份给他人时才导出静态版：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json --out "300308_中际旭创_2026中报_财报分析_YYYYMMDD.html"
```
```

同时把「### 5. 交付」中的「报告路径」表述改为「viewer 链接 http://localhost:8765/viewer.html + 报告文件名」。

- [ ] **Step 4: 镜像同步 + 全量回归**

```bash
cp "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" D:/code/yeji/skill_deploy/scripts/render_report.py
cp "C:/Users/35033/.claude/skills/fin-report/SKILL.md" D:/code/yeji/skill_deploy/SKILL.md
cd D:/code/yeji && python -X utf8 -m pytest -q
```

Expected: 全部通过（17 个既有 + 7 个新增）。

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: skill渲染链切换报告中心并更新文档"
```

---

## 验收总清单（对照 spec）

1. ✅ 新分析落盘 JSON 进 reports/ 并出现在 viewer 列表（Task 4 Step 2）
2. ✅ 同公司同报告期覆盖不重复（Task 2/4 去重断言）
3. ✅ viewer 列表点选/搜索/切换/导出可用（Task 3 Step 3 人眼）
4. ✅ file:// 直开有黄条引导（Task 3 人眼：临时改名 index.json 或断服务验证）
5. ✅ 单个 JSON 损坏不影响其他（Task 3 openReport catch 分支）
6. ✅ 旧静态导出路径保留（Task 4 --out）
