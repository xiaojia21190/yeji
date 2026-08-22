# 财报分析 Skill（fin-report）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建全局 skill `fin-report`：输入 A 股代码，产出「业绩 vs 机构预期对照 + 趋势质量 + 同行对比 + 估值」四模块 HTML 报告。

**Architecture:** skill 目录 `C:\Users\35033\.claude\skills\fin-report\`，Python 脚本只管稳定取数（新浪系 akshare 接口为主，已验证绕过东财 push2 不稳定问题），分析判断由 AI 按 SKILL.md 流程在会话内完成，HTML 报告用模板渲染。开发与测试在 `D:\code\yeji`。

**Tech Stack:** Python 3.13 + akshare 1.18.27（已装）+ pytest 9.0.2（已装）。无需新依赖。

**已验证的数据源事实（实现时直接依赖，勿再探索）：**

| 数据 | 接口 | 状态 |
|---|---|---|
| 财务摘要多期（归母/扣非/营收/毛利率/ROE/现金流） | `ak.stock_financial_abstract(symbol='300308')` | ✅ 稳定，新浪源，单位为元 |
| 利润表/资产负债表全科目 | `ak.stock_financial_report_sina(stock='sz300308', symbol='利润表'\|'资产负债表')` | ✅ 稳定；资产负债表含 `实收资本(或股本)` |
| 机构研报预测（评级/EPS预测/日期/PDF链接） | `ak.stock_research_report_em(symbol='300308')` | ✅ 稳定（东财 pdf.dfcfw.com 域名不受影响）；`2026-盈利预测-收益` 是 EPS 元口径 |
| 日线行情+流通股本 | `ak.stock_zh_a_daily(symbol='sz300308', ...)` | ✅ 稳定，新浪源，含 `outstanding_share` |
| 实时/快照行情 | `requests.get('https://hq.sinajs.cn/list=sz300308', headers={'Referer':'https://finance.sina.com.cn'})` | ✅ 稳定，GBK 编码 |
| 申万一/二级行业列表 | `ak.sw_index_first_info()` / `ak.sw_index_second_info()` | ✅ 稳定（通信 801770.SI / 通信设备 801102.SI） |
| 东财 push2 系（个股信息/行业成分/历史行情） | — | ❌ 本机代理环境下间歇性 Connection refused，**禁用** |
| 申万成分明细接口 | `ak.sw_index_third_cons` | ❌ pandas 解析 bug + 官网被拦，**禁用**；同行清单由 AI 用 WebSearch 定夺 |

**环境注意：** 本机 `HTTP_PROXY=http://127.0.0.1:7890`。新浪系接口走代理正常；若遇 ProxyError，在脚本内用 `proxies={'http': None, 'https': None}` 直连重试一次（hq.sinajs.cn 直连已验证可行）。所有 Python 命令统一用 `python -X utf8`（Windows GBK 控制台防乱码）。

**测试策略（Level 判定）：** 纯函数（季度拆解、季节系数、达标判定、市值换算）走 TDD（Level 2，有回归价值）；取数脚本用「真接口冒烟 + 结构断言」（不打 mock，接口本身已人工验证）；模板渲染用 golden 结构断言。akshare 真接口测试标记 `@pytest.mark.net`，网络抖动时可 `-m "not net"` 跳过。

---

## 文件结构总览

```
D:\code\yeji\                              ← 开发测试工作区
├── docs\specs\2026-08-22-fin-report-skill-design.md   （已有）
├── docs\plans\2026-08-22-fin-report-skill.md          （本计划）
├── tests\
│   ├── test_quarter_math.py     ← Task 2 季度拆解/系数/判定纯函数
│   ├── test_fetch_financial.py  ← Task 3 财务取数冒烟
│   ├── test_fetch_forecast.py   ← Task 4 预测取数冒烟
│   ├── test_fetch_market.py     ← Task 5 行情取数冒烟
│   └── test_render_report.py    ← Task 6 渲染纯函数
├── finreport\                    ← 可复用库（skill 脚本 import 它）
│   ├── __init__.py
│   ├── quarter_math.py           ← 纯函数：季度拆解/季节系数/达标判定
│   └── http.py                   ← 带重试的 GET 封装（代理降级）
└── reports\                      ← 报告产出目录
    └── .gitkeep

C:\Users\35033\.claude\skills\fin-report\   ← 最终 skill（Task 7-8 部署）
├── SKILL.md
├── scripts\
│   ├── fetch_financial.py
│   ├── fetch_forecast.py
│   ├── fetch_market.py
│   └── render_report.py
└── references\
    ├── methodology.md
    ├── metrics.md
    └── report-template.html
```

**依赖方向：** skill 脚本 → `finreport` 库 → 无内部依赖。skill 脚本通过 `sys.path.insert` 引用 `D:\code\yeji\finreport`（见 Task 7 的 bootstrap 片段）。

---

### Task 1: 初始化工作区

**Files:**
- Create: `D:\code\yeji\finreport\__init__.py`
- Create: `D:\code\yeji\reports\.gitkeep`
- Create: `D:\code\yeji\pytest.ini`

- [ ] **Step 1: 创建目录骨架与空文件**

```bash
mkdir -p D:/code/yeji/finreport D:/code/yeji/reports D:/code/yeji/tests
touch D:/code/yeji/finreport/__init__.py D:/code/yeji/reports/.gitkeep
```

- [ ] **Step 2: 写 pytest.ini**

`D:\code\yeji\pytest.ini`：

```ini
[pytest]
markers =
    net: 需要真实网络的冒烟测试（可 -m "not net" 跳过）
testpaths = tests
```

- [ ] **Step 3: 验证 pytest 可发现空测试目录**

Run: `cd D:/code/yeji && python -X utf8 -m pytest --collect-only -q`
Expected: `no tests ran`（收集为空，无报错）

- [ ] **Step 4: Commit**

```bash
cd D:/code/yeji && git init -b main 2>/dev/null; git add -A && git commit -m "chore: 初始化财报分析skill工作区"
```

---

### Task 2: 季度拆解与达标判定纯函数（TDD）

**Files:**
- Create: `D:\code\yeji\finreport\quarter_math.py`
- Test: `D:\code\yeji\tests\test_quarter_math.py`

- [ ] **Step 1: 写失败测试**

`D:\code\yeji\tests\test_quarter_math.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_quarter_math.py -q`
Expected: FAIL（`ModuleNotFoundError: finreport.quarter_math`）

- [ ] **Step 3: 实现 quarter_math.py**

`D:\code\yeji\finreport\quarter_math.py`：

```python
"""财报对照核心算式：单季拆解、季节系数反推、达标判定、市值换算。

金额单位约定：函数入参/返回值一律为「元」（与 akshare 新浪源一致），
展示层用 fmt_yi 转亿元。
"""
from __future__ import annotations

# 达标判定的相对容差：|实际-预期|/预期 ≤ 2% 视为达标
TOLERANCE = 0.02


def single_quarter(cum_curr: float, cum_prev: float) -> float:
    """累计值拆单季：当期累计 - 上期累计。如 H1 - Q1 = Q2。"""
    return cum_curr - cum_prev


def season_ratio(h1_prior: float, annual_prior: float) -> float | None:
    """季节系数：上一年 H1 占全年比例。全年为 0/缺失时返回 None。"""
    if not annual_prior:
        return None
    return h1_prior / annual_prior


def backcast(annual_forecast: float, ratio: float | None, q1_actual: float) -> float | None:
    """反推单季：全年预测 × 季节系数 - Q1 实际。系数缺失时返回 None。"""
    if ratio is None or not annual_forecast:
        return None
    return annual_forecast * ratio - q1_actual


def verdict(actual: float, expected: float, tolerance: float = TOLERANCE) -> tuple[str, float]:
    """达标判定。返回 (状态, 差额=实际-预期)。实际高于预期且在容差内或超出均算达标。"""
    diff = actual - expected
    if expected == 0:
        return ("未达标", diff)
    if abs(diff) / abs(expected) <= tolerance:
        return ("达标", diff)
    # 实际 >= 预期（超预期）视为达标；低于预期超出容差为未达标
    state = "达标" if diff > 0 else "未达标"
    return (state, diff)


def calc_market_cap(shares: float, price: float) -> float:
    """总市值（元）= 总股本 × 现价。"""
    return shares * price


def fmt_yi(value: float | None, ndigits: int = 2) -> str:
    """元 → 亿元字符串，缺失返回 —。"""
    if value is None:
        return "—"
    return f"{value / 1e8:.{ndigits}f}"
```

- [ ] **Step 4: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_quarter_math.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 季度拆解与达标判定纯函数"
```

---

### Task 3: 带重试的 HTTP 封装 + 财务取数脚本

**Files:**
- Create: `D:\code\yeji\finreport\http.py`
- Test: `D:\code\yeji\tests\test_fetch_financial.py`

- [ ] **Step 1: 实现 http.py（代理降级重试）**

`D:\code\yeji\finreport\http.py`：

```python
"""带代理降级的 GET：先默认（可能走系统代理），ProxyError/ConnectionError 时直连重试。"""
from __future__ import annotations

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def get_with_fallback(url: str, *, params=None, headers=None, timeout=15) -> requests.Response:
    """GET：默认走环境代理，失败后绕过代理直连一次。两次都失败抛最后异常。"""
    base_headers = {"User-Agent": UA}
    if headers:
        base_headers.update(headers)
    last_exc: Exception | None = None
    for proxies in (None, {"http": None, "https": None}):
        try:
            resp = requests.get(
                url, params=params, headers=base_headers,
                timeout=timeout, proxies=proxies,
            )
            resp.raise_for_status()
            return resp
        except (requests.exceptions.ProxyError,
                requests.exceptions.ConnectionError) as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 2: 写取数冒烟测试（真接口，标记 net）**

`D:\code\yeji\tests\test_fetch_financial.py`：

```python
"""fetch_financial 冒烟：结构断言 + 已人工验证的锚点数字（300308 中际旭创 2026 中报）。"""
import subprocess
import sys
import json
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.net

ANCHOR = {  # 2026-06-30 报告期锚点（元）
    "归母净利润": 1.365115e10,
    "扣非净利润": 1.309160e10,
    "营业总收入": 4.177786e10,
}


def run_fetch(code: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from finreport.fetch_dev import fetch_abstract_dict; "
         "import json; print(json.dumps(fetch_abstract_dict('%s')))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_abstract_anchor_300308():
    data = run_fetch("300308")
    periods = data["periods"]
    assert "20260630" in periods and "20260331" in periods
    for metric, expected in ANCHOR.items():
        actual = data["series"][metric]["20260630"]
        assert actual == pytest.approx(expected, rel=2e-3), metric
```

注：测试通过 `finreport.fetch_dev.fetch_abstract_dict` 调用——开发期先在 `finreport/` 下实现同名逻辑，Task 7 部署 skill 脚本时直接复用同一文件内容。

- [ ] **Step 3: 写开发期取数模块 fetch_dev.py**

`D:\code\yeji\finreport\fetch_dev.py`：

```python
"""开发期取数实现：财务摘要 → 标准化 dict。skill 部署时整体复制到 scripts/fetch_financial.py。"""
from __future__ import annotations

import akshare as ak

# 报告关心的指标（对应 stock_financial_abstract 的「指标」列，名称已实测核对）
WANTED = [
    "归母净利润", "扣非净利润", "营业总收入", "经营现金流量净额",
    "毛利率", "净资产收益率(ROE)", "基本每股收益",
]


def fetch_abstract_dict(code: str) -> dict:
    """返回 {periods: [...], series: {指标: {报告日: 值(元或比率)}}}。"""
    df = ak.stock_financial_abstract(symbol=code)
    period_cols = [c for c in df.columns if c not in ("选项", "指标") and c.isdigit()]
    series: dict[str, dict[str, float]] = {}
    for metric in WANTED:
        rows = df[df["指标"] == metric]
        if rows.empty:
            continue
        row = rows.iloc[0]
        values = {}
        for col in period_cols:
            v = row[col]
            if v is not None and v != "False" and v != "-" and str(v).strip() != "":
                try:
                    values[col] = float(v)
                except (TypeError, ValueError):
                    pass
        series[metric] = values
    return {"periods": sorted(period_cols, reverse=True), "series": series}
```

- [ ] **Step 4: 运行冒烟测试**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_fetch_financial.py -v`
Expected: 1 passed（约 10-30 秒，真接口）

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 财务摘要取数与HTTP代理降级封装"
```

---

### Task 4: 机构预测取数脚本

**Files:**
- Create: `D:\code\yeji\finreport\fetch_forecast_dev.py`
- Test: `D:\code\yeji\tests\test_fetch_forecast.py`

- [ ] **Step 1: 写冒烟测试（锚点：交银国际 7/22 研报 EPS 29.119）**

`D:\code\yeji\tests\test_fetch_forecast.py`：

```python
"""机构预测取数冒烟：东财研报列表。锚点=交银国际 2026-07-22 EPS 29.119（已人工验证）。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.net


def run_fetch(code: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from finreport.fetch_forecast_dev import fetch_reports; "
         "import json; print(json.dumps(fetch_reports('%s'), ensure_ascii=False))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_reports_contain_jiaoyin_anchor():
    data = run_fetch("300308")
    reports = data["reports"]
    assert len(reports) >= 5
    jy = [r for r in reports if "交银" in r["org"]]
    assert jy, "应含交银国际研报"
    latest = jy[0]  # 按日期降序的第一条
    assert latest["eps_2026"] == pytest.approx(29.119, rel=1e-3)
    assert latest["rating"] == "买入"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_fetch_forecast.py -q`
Expected: FAIL（`ModuleNotFoundError: finreport.fetch_forecast_dev`）

- [ ] **Step 3: 实现 fetch_forecast_dev.py**

`D:\code\yeji\finreport\fetch_forecast_dev.py`：

```python
"""机构研报预测取数：东财研报列表 → 标准化列表（EPS 口径，元）。"""
from __future__ import annotations

import akshare as ak


def fetch_reports(code: str) -> dict:
    """返回 {reports: [{org, rating, date, eps_2026, eps_2027, title, pdf_url}]}，按日期降序。"""
    df = ak.stock_research_report_em(symbol=code)
    reports = []
    for _, row in df.iterrows():
        reports.append({
            "org": str(row.get("机构", "")),
            "rating": str(row.get("东财评级", "")),
            "date": str(row.get("日期", "")),
            "eps_2026": _to_float(row.get("2026-盈利预测-收益")),
            "eps_2027": _to_float(row.get("2027-盈利预测-收益")),
            "title": str(row.get("报告名称", "")),
            "pdf_url": str(row.get("报告PDF链接", "")),
        })
    reports.sort(key=lambda r: r["date"], reverse=True)
    return {"reports": reports}


def _to_float(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN -> None
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_fetch_forecast.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 机构研报预测取数脚本"
```

---

### Task 5: 行情与股本取数脚本

**Files:**
- Create: `D:\code\yeji\finreport\fetch_market_dev.py`
- Test: `D:\code\yeji\tests\test_fetch_market.py`

- [ ] **Step 1: 写冒烟测试（锚点：收盘 943.0 / 流通股本 11.10 亿 / 总股本 1115234641）**

`D:\code\yeji\tests\test_fetch_market.py`：

```python
"""行情股本取数冒烟。锚点=2026-08-21 收盘 943.0、流通股本 11.0994 亿股、
2026-06-30 总股本（实收资本）1115234641。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DEV = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.net


def run_fetch(code: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from finreport.fetch_market_dev import fetch_market; "
         "import json; print(json.dumps(fetch_market('%s'), ensure_ascii=False))" % (SKILL_DEV, code)],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_market_anchors():
    data = run_fetch("300308")
    # 实时价锚点：中际旭创 943 元上下（允许近期波动 ±15%）
    assert 800 <= data["price"] <= 1100
    assert data["date"], "应含行情日期"
    # 总股本锚点：资产负债表实收资本（2026-06-30 = 1115234641，股本短期不变）
    assert data["total_shares"] == pytest.approx(1115234641, rel=1e-3)
    # 总市值 = 股本 × 现价
    assert data["total_market_cap"] == pytest.approx(
        data["total_shares"] * data["price"], rel=1e-6)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_fetch_market.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 fetch_market_dev.py**

`D:\code\yeji\finreport\fetch_market_dev.py`：

```python
"""行情与股本取数：新浪实时行情 + 最新日线兜底 + 资产负债表实收资本（总股本）。

禁用东财 push2 系接口（本机代理环境间歇性拒连，见计划头部事实表）。
"""
from __future__ import annotations

import datetime as dt

import akshare as ak

from .http import get_with_fallback


def fetch_market(code: str, latest_period: str | None = None) -> dict:
    """返回 {price, date, total_shares, total_market_cap}。

    code: 6 位纯数字；latest_period: 报告期 YYYYMMDD，用于对齐实收资本行。
    """
    price, date = _realtime_price(code)
    if price is None:
        price, date = _daily_last_price(code)
    shares = _total_shares(code, latest_period)
    return {
        "price": price,
        "date": date,
        "total_shares": shares,
        "total_market_cap": shares * price if (shares and price) else None,
    }


def _prefix(code: str) -> str:
    return ("sh" if code.startswith(("6", "9", "5")) else
            "bj" if code.startswith(("4", "8")) else "sz") + code


def _realtime_price(code: str) -> tuple[float | None, str]:
    """新浪实时行情：hq.sinajs.cn，GBK，需 Referer。返回 (价格, YYYY-MM-DD)。"""
    resp = get_with_fallback(
        f"https://hq.sinajs.cn/list={_prefix(code)}",
        headers={"Referer": "https://finance.sina.com.cn"},
    )
    text = resp.content.decode("gbk", errors="replace")
    # 格式: var hq_str_sz300308="名称,今开,昨收,现价,...,日期,时间";
    parts = text.split('"')[1].split(",")
    try:
        price = float(parts[3])
    except (IndexError, ValueError):
        return None, ""
    date = parts[30] if len(parts) > 30 else ""
    return price, date


def _daily_last_price(code: str) -> tuple[float, str]:
    """新浪日线兜底：取最近 5 个自然日内最后一根收盘。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=5)
    df = ak.stock_zh_a_daily(
        symbol=_prefix(code),
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    last = df.iloc[-1]
    return float(last["close"]), str(last["date"])


def _total_shares(code: str, latest_period: str | None) -> float | None:
    """总股本 = 资产负债表最新一期「实收资本(或股本)」(元面值 1 元即股数)。"""
    df = ak.stock_financial_report_sina(stock=_prefix(code), symbol="资产负债表")
    if latest_period:
        hit = df[df["报告日"] == latest_period]
        if not hit.empty:
            v = hit.iloc[0].get("实收资本(或股本)")
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    v = df.iloc[0].get("实收资本(或股本)")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_fetch_market.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: 行情与总股本取数脚本"
```

---

### Task 6: HTML 模板与渲染脚本

**Files:**
- Create: `C:\Users\35033\.claude\skills\fin-report\references\report-template.html`（同时复制到 `D:\code\yeji\finreport\report-template.html` 供测试）
- Create: `D:\code\yeji\finreport\render_dev.py`
- Test: `D:\code\yeji\tests\test_render_report.py`

- [ ] **Step 1: 写渲染纯函数测试**

`D:\code\yeji\tests\test_render_report.py`：

```python
"""render_dev 渲染测试：用最小数据集断言 HTML 结构与关键内容。"""
import json
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
    assert 'class="tag good"' in html or "tag good" in html
    assert "tag bad" in html
    # 单文件无外部依赖
    assert "<script src" not in html and 'link rel="stylesheet"' not in html


def test_render_table_row_tones():
    html = render_report(MINIMAL, template_path=str(TPL))
    assert 'tone="bad"' not in html  # tone 已转成 class，不泄漏原属性
    assert html.count("<table") >= 1
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_render_report.py -q`
Expected: FAIL（ModuleNotFoundError + 模板不存在）

- [ ] **Step 3: 写 report-template.html**

模板用占位符 `{{JSON_PAYLOAD}}` 方式：渲染函数把数据 JSON 注入 + 服务端拼表格。写到 `D:\code\yeji\finreport\report-template.html`（Task 7 复制到 skill）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
  :root {
    --ink: #1f2430; --sub: #6b7280; --line: #e5e7eb; --bg: #f7f8fa;
    --good: #0b7a3e; --good-bg: #e8f6ee; --bad: #b3123f; --bad-bg: #fdeef2;
    --accent: #1d4ed8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; color: var(--ink);
         background: var(--bg); line-height: 1.6; padding: 24px; }
  .wrap { max-width: 1080px; margin: 0 auto; }
  header { border-bottom: 2px solid var(--ink); padding-bottom: 12px; margin-bottom: 16px; }
  .crumb { color: var(--sub); font-size: 13px; }
  h1 { font-size: 26px; margin: 6px 0; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
  .chip { font-size: 12px; color: var(--accent); border: 1px solid #c7d7f8;
          border-radius: 999px; padding: 2px 10px; background: #fff; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
           gap: 12px; margin: 16px 0; }
  .card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 14px; }
  .card .label { font-size: 13px; color: var(--sub); }
  .card .value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; margin: 4px 0; }
  .tag { display: inline-block; font-size: 12px; border-radius: 6px; padding: 2px 8px; }
  .tag.good { color: var(--good); background: var(--good-bg); }
  .tag.bad { color: var(--bad); background: var(--bad-bg); }
  .tag.warn { color: #8a6d00; background: #fdf6e3; }
  section { background: #fff; border: 1px solid var(--line); border-radius: 10px;
            padding: 18px; margin: 14px 0; }
  section h2 { font-size: 17px; margin-bottom: 8px; }
  section .intro { color: var(--sub); font-size: 13px; margin-bottom: 10px; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin: 8px 0; }
  th { text-align: left; color: var(--sub); font-weight: 600; border-bottom: 1px solid var(--ink);
       padding: 6px 8px; white-space: nowrap; }
  td { border-bottom: 1px solid var(--line); padding: 6px 8px;
       font-variant-numeric: tabular-nums; }
  tr.row-bad td { background: var(--bad-bg); }
  tr.row-good td { background: var(--good-bg); }
  .conclusion { border-radius: 8px; padding: 10px 12px; font-size: 14px; margin-top: 8px; }
  .conclusion.good { background: var(--good-bg); color: var(--good); }
  .conclusion.bad { background: var(--bad-bg); color: var(--bad); }
  .note { color: var(--sub); font-size: 12.5px; margin-top: 6px; }
  footer { color: var(--sub); font-size: 12px; border-top: 1px solid var(--line);
           margin-top: 20px; padding-top: 10px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="crumb">{{META.code}}.SZ · {{META.period_label}} · 业绩符合预期情况</div>
    <h1>{{META.name}} {{META.period_label}} 财报分析</h1>
    <div class="chips">
      <span class="chip">只列事实与数字</span>
      <span class="chip">机构预测逐家溯源</span>
      <span class="chip">反推算式可查</span>
      <span class="chip">已剔除无原文依据机构</span>
    </div>
  </header>

  <div class="cards">
    {{CARDS}}
  </div>

  {{SECTIONS}}

  <footer>
    生成于 {{META.generated}} · {{META.disclaimer}}
  </footer>
</div>
</body>
</html>
```

- [ ] **Step 4: 实现 render_dev.py**

`D:\code\yeji\finreport\render_dev.py`：

```python
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
    html = html.replace("{{META.code}}", escape(meta["code"]))
    html = html.replace("{{META.period_label}}", escape(meta["period_label"]))
    html = html.replace("{{META.name}}", escape(meta["name"]))
    html = html.replace("{{META.generated}}", escape(meta["generated"]))
    html = html.replace("{{META.disclaimer}}", escape(meta["disclaimer"]))
    html = html.replace("{{CARDS}}", _render_cards(data.get("cards", [])))
    html = html.replace("{{SECTIONS}}", _render_sections(data.get("sections", [])))
    return html


def _render_cards(cards: list[dict]) -> str:
    parts = []
    for c in cards:
        parts.append(
            f'<div class="card"><div class="label">{escape(str(c["label"]))}</div>'
            f'<div class="value">{escape(str(c["value"]))}</div>'
            f'<span class="tag {escape(str(c.get("tone", "warn")))}">'
            f'{escape(str(c.get("tag", "")))}</span></div>'
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
            body.append(_render_table(table))
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
```

- [ ] **Step 5: 运行确认通过**

Run: `cd D:/code/yeji && python -X utf8 -m pytest tests/test_render_report.py -v`
Expected: 2 passed（离线，无 net 标记）

- [ ] **Step 6: 人眼验收最小报告**

```bash
cd D:/code/yeji && python -X utf8 -c "
from pathlib import Path
import sys; sys.path.insert(0, '.')
from tests.test_render_report import MINIMAL
from finreport.render_dev import render_report
Path('reports/_smoke.html').write_text(render_report(MINIMAL), encoding='utf-8')
print('written reports/_smoke.html')
" && start "" "D:/code/yeji/reports/_smoke.html"
```

Expected: 浏览器打开，卡片/表格/色块/结论框布局正确（对照参考图风格）。

- [ ] **Step 7: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "feat: HTML报告模板与渲染器"
```

---

### Task 7: 部署 skill（SKILL.md + scripts + references）

**Files:**
- Create: `C:\Users\35033\.claude\skills\fin-report\SKILL.md`
- Create: `C:\Users\35033\.claude\skills\fin-report\scripts\fetch_financial.py`（fetch_dev.py 内容 + CLI）
- Create: `C:\Users\35033\.claude\skills\fin-report\scripts\fetch_forecast.py`
- Create: `C:\Users\35033\.claude\skills\fin-report\scripts\fetch_market.py`
- Create: `C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py`
- Create: `C:\Users\35033\.claude\skills\fin-report\references\methodology.md`
- Create: `C:\Users\35033\.claude\skills\fin-report\references\metrics.md`
- Create: `C:\Users\35033\.claude\skills\fin-report\references\report-template.html`（Task 6 模板复制）
- Test: 手工验证 `--help` 输出

- [ ] **Step 1: 创建 skill 目录并复制模板**

```bash
mkdir -p "C:/Users/35033/.claude/skills/fin-report/scripts" "C:/Users/35033/.claude/skills/fin-report/references"
cp D:/code/yeji/finreport/report-template.html "C:/Users/35033/.claude/skills/fin-report/references/report-template.html"
```

- [ ] **Step 2: 写 fetch_financial.py（skill 版 = fetch_dev + CLI）**

`C:\Users\35033\.claude\skills\fin-report\scripts\fetch_financial.py`：

```python
"""财报数据取数 CLI：python fetch_financial.py 300308 [--period 20260630] [--out data.json]

输出 JSON：{periods, series, balance: {total_shares, period}}。新浪源，单位元。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"  # finreport 库位置

sys.path.insert(0, LIB)

from finreport.fetch_dev import fetch_abstract_dict  # noqa: E402
from finreport.fetch_market_dev import _total_shares  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="财报数据取数（新浪源）")
    ap.add_argument("code", help="6 位股票代码，如 300308")
    ap.add_argument("--period", default=None, help="报告期 YYYYMMDD，用于对齐股本")
    ap.add_argument("--out", default=None, help="输出 JSON 路径，缺省打印 stdout")
    args = ap.parse_args()

    data = fetch_abstract_dict(args.code)
    try:
        data["balance"] = {"total_shares": _total_shares(args.code, args.period),
                           "period": args.period}
    except Exception as exc:  # 股本失败不阻塞主数据
        data["balance"] = {"total_shares": None, "period": args.period,
                           "error": str(exc)[:200]}
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 写 fetch_forecast.py（skill 版）**

`C:\Users\35033\.claude\skills\fin-report\scripts\fetch_forecast.py`：

```python
"""机构预测取数 CLI：python fetch_forecast.py 300308 [--out forecast.json]

输出 JSON：{reports: [{org, rating, date, eps_2026, eps_2027, title, pdf_url}]}。
EPS 为元口径；净利 = EPS × 总股本 由分析阶段换算。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.fetch_forecast_dev import fetch_reports  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="机构研报预测取数（东财研报列表）")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = fetch_reports(args.code)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 写 fetch_market.py（skill 版）**

`C:\Users\35033\.claude\skills\fin-report\scripts\fetch_market.py`：

```python
"""行情与市值 CLI：python fetch_market.py 300308 [--period 20260630] [--out market.json]

输出 JSON：{price, date, total_shares, total_market_cap}。
"""
from __future__ import annotations

import argparse
import json
import sys

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.fetch_market_dev import fetch_market  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="行情与总市值取数")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--period", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = fetch_market(args.code, args.period)
    text = json.dumps(data, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 写 render_report.py（skill 版）**

`C:\Users\35033\.claude\skills\fin-report\scripts\render_report.py`：

```python
"""报告渲染 CLI：python render_report.py payload.json [--out report.html] [--open]

payload.json 结构见 references/report-template.html 与 SKILL.md 附录。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIB = r"D:\code\yeji"

sys.path.insert(0, LIB)

from finreport.render_dev import render_report  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "report-template.html"


def main() -> None:
    ap = argparse.ArgumentParser(description="财报分析 HTML 报告渲染")
    ap.add_argument("payload", help="payload JSON 路径")
    ap.add_argument("--out", default=None, help="输出 HTML 路径")
    ap.add_argument("--open", action="store_true", help="渲染后用默认浏览器打开")
    args = ap.parse_args()

    data = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    html = render_report(data, template_path=str(TEMPLATE))
    out = Path(args.out) if args.out else Path(args.payload).with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"written {out}")
    if args.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 写 methodology.md**

`C:\Users\35033\.claude\skills\fin-report\references\methodology.md`：

```markdown
# 反推对照方法论

## 核心算式

1. 单季拆解：`Q2 = H1累计 − Q1累计`（Q4 = 年度 − Q3累计）
2. 季节系数：`ratio = 上年H1 / 上年全年`（用公司自身历史节奏；参考报告用 39.2% 净利 / 43.4% 营收）
3. 反推：`机构Q2预期 = 机构全年预测 × ratio − Q1实际`
4. EPS 口径换算：`净利预测 = EPS预测 × 最新总股本`（总股本取资产负债表实收资本，如 300308 = 11.15234641 亿股）

## 季节系数的三种取法（优先级从高到低）

1. **原文校准**：机构研报原文给出单季/H1 值 → 直接用
2. **历史同期**：公司上年 H1/全年占比（本 skill 默认）
3. **区间对照**：系数无法确定时，不反推点值，改为「实际 vs 全年×[0.35, 0.45]」区间判断，报告中明示局限

## 达标判定

- 相对容差 ±2% 内 → 达标
- 实际 > 预期（超预期）→ 达标
- 实际 < 预期且超容差 → 未达标
- 差额 = 实际 − 预期，报告精确列示

## 溯源纪律

- 每个机构数字必须有出处：akshare 研报列表（含 PDF 链接）或 WebSearch 可溯源的新闻稿
- 无原文依据的预测一律剔除并在报告注明
- 两个来源冲突 → 并列列出，不擅自取舍
- 外资行（高盛/大摩/野村/瑞银）预测 akshare 无 → WebSearch 搜「公司名 机构名 目标价/净利润 预测」

## 归母 vs 扣非差额拆解

差额 = 非经常性损益。明细科目取利润表附注/财报「非经常性损益」表：
委托理财收益、政府补助、公允价值变动、处置收益、营业外收支、所得税/少数股东影响。
Q2 单季差额 = Q2归母 − Q2扣非。

## 毛利率判定

市场区间（如 45~47%）为区间判定而非点值；机构隐含值（全年毛利率 × 季节节奏）单独一行对照。
单季毛利率 = (累计营收 − 累计营业成本) 差额法：`Q2毛利率 = (H1毛利 − Q1毛利) / (H1营收 − Q1营收)`。
```

- [ ] **Step 7: 写 metrics.md**

`C:\Users\35033\.claude\skills\fin-report\references\metrics.md`：

```markdown
# 指标口径字典

## 单位约定

- akshare 新浪财务源金额单位为**元**；报告展示统一**亿元**（fmt_yi，两位小数）
- 比率类（毛利率/ROE）为百分数值（46.42 表示 46.42%）
- EPS 单位元

## 核心指标口径

| 指标 | akshare 字段（stock_financial_abstract「指标」列） | 说明 |
|---|---|---|
| 归母净利润 | 归母净利润 | 元 |
| 扣非净利润 | 扣非净利润 | 元 |
| 营收 | 营业总收入 | 元；个别公司无该行时降级用「营业收入」 |
| 经营现金流 | 经营现金流量净额 | 元 |
| 毛利率 | 毛利率 | %；若无则 (营收−营业成本)/营收 自算 |
| ROE | 净资产收益率(ROE) | %，加权口径 |
| EPS | 基本每股收益 | 元 |

## 每期报告期代码

YYYYMMDD：0331=Q1、0630=H1、0930=Q3、1231=年度。累计口径：H1 含 Q1Q2，Q3 含前三季。

## 财务质量信号（趋势模块用）

- 经营现金流/归母净利 < 0.5 连续两期 → 盈利质量预警
- 应收增速 > 营收增速 × 1.5 → 回款恶化
- 存货增速 > 营收增速 × 2 且毛利率下行 → 滞销风险
- 毛利率单季环比变动 > ±3pct → 标注

## 杜邦拆解

ROE = 净利率 × 总资产周转率 × 权益乘数。
净利率=归母净利/营收；周转率=营收/总资产(期末)；权益乘数=总资产/归母净资产。
取年度或 TTM 口径，趋势模块列近 3 年变动来源。

## 估值口径

- PE-TTM = 总市值 / 近四季归母净利和
- PE-2026E = 总市值 / (EPS2026 预测 × 总股本)
- 只列事实：对应哪家机构哪年预测多少倍，不给买卖建议
```

- [ ] **Step 8: 写 SKILL.md**

`C:\Users\35033\.claude\skills\fin-report\SKILL.md`：

```markdown
---
name: fin-report
description: A 股财报分析：业绩 vs 机构预期对照（反推算式可查）、财务趋势与质量、同行横向对比、估值水平。输入股票代码产出单文件 HTML 报告。触发词：/fin-report、财报分析、中报/年报/季报对照预期、业绩是否符合预期。
---

# 财报分析（fin-report）

输入 A 股代码，产出四模块单文件 HTML 报告。**声明：本次使用 fin-report skill。**

## 执行流程

### 0. 解析输入

- 参数：股票代码（6 位）必需；可选 `--period=YYYYMMDD`、`--modules=expectation,trend,peers,valuation`（默认全部）
- 通过 akshare `stock_individual_info_em` 不可用时，直接用财务摘要接口确认代码有效并取公司名

### 1. 取数（脚本，稳定数据）

统一在当前工作目录建 `finreport_work/` 缓存：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_financial.py" 300308 --period 20260630 --out finreport_work/financial.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" 300308 --out finreport_work/forecast.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_market.py" 300308 --period 20260630 --out finreport_work/market.json
```

任一脚本失败：重试 1 次；仍失败则报告相应模块降级（预期对照缺 forecast → 该模块输出「无可靠预测，跳过」），绝不编数。

### 2. 补数（WebSearch，外资行与复核）

- 外资行（高盛/大摩/野村/瑞银/美银等）全年预测与目标价：搜「公司名+机构名+净利润 预测/目标价」，只收录有明确原文出处的，记录 URL
- 同行清单：WebSearch「公司名 同行业 可比上市公司」，结合研报列表行业字段定 3~6 家
- 两源冲突：并列列出，不取舍

### 3. 分析（AI，按 references/methodology.md）

- 单季拆解、季节系数、反推、达标判定：算式全部写进报告
- 逐机构对照表：机构/评级/全年预测/反推Q2/差额/判定
- 归母−扣非差额拆非经常性损益明细
- 趋势模块：近 8 期序列+单季环比+质量信号（references/metrics.md 信号表）
- 同行模块：增速/毛利率/ROE 对比表（同行数据同样用 fetch_financial.py 取）
- 估值模块：PE-TTM、PE-2026E/2027E 逐机构

### 4. 渲染（脚本）

payload 结构：meta{code,name,period_label,generated,disclaimer} + cards[] + sections[]{title,intro,tables[],conclusion{tone,text},notes[]}。
tone: good/bad/warn；表格 rows 与 row_tones 等长对齐。

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json --out "300308_中际旭创_2026中报_财报分析_YYYYMMDD.html" --open
```

文件名：`{代码}_{公司名}_{报告期}label_财报分析_{当天YYYYMMDD}.html`，输出到当前目录。

### 5. 交付

- 报告路径 + 3~5 句核心结论（四模块各一句）
- 数据全部可溯源：机构数字标来源，反推算式在附录

## 硬性纪律

- 只列事实与数字，不构成投资建议（报告尾注固定声明）
- 无原文依据的机构预测一律剔除并注明
- 单位换算错误零容忍：脚本输出元，报告亿元，反推前先统一
- 东财 push2 系接口本机不可用，勿调 ak.stock_bid_ask_em / stock_individual_info_em / stock_board_industry_cons_em / stock_zh_a_hist
```

- [ ] **Step 9: 验证 skill 脚本可跑**

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_financial.py" --help
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" --help
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_market.py" --help
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" --help
```

Expected: 四个脚本均打印 usage 无报错。

再各跑一次真数据（输出到临时文件后删除）：

```bash
cd D:/code/yeji && mkdir -p finreport_work
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" 300308 --out finreport_work/_t.json && head -c 300 finreport_work/_t.json && rm finreport_work/_t.json
```

Expected: JSON 含「交银国际证券」与 29.119。

- [ ] **Step 10: Commit（yeji 仓库记档 skill 部署内容副本）**

将 skill 目录内容镜像到 `D:\code\yeji\skill_deploy\`（便于版本管理，skill 安装目录本身不在 git 内）：

```bash
mkdir -p D:/code/yeji/skill_deploy
cp -r "C:/Users/35033/.claude/skills/fin-report/." D:/code/yeji/skill_deploy/
cd D:/code/yeji && git add -A && git commit -m "feat: 部署fin-report skill并入库镜像"
```

---

### Task 8: 300308 全流程验收（对照参考报告）

**Files:**
- Create: `D:\code\yeji\finreport_work\payload.json`（过程产物）
- Create: `D:\code\yeji\300308_中际旭创_2026中报_财报分析_*.html`（验收产物）

- [ ] **Step 1: 按新会话视角执行 SKILL.md 流程**

以 executor 身份严格按 SKILL.md 步骤 0→5 跑 300308 全流程（代码在同一会话中执行即可，但流程步骤一步不跳）。

- [ ] **Step 2: 数字核对（与参考报告/已验证锚点对照）**

逐项断言（人工核对报告 HTML 内容）：

| 项 | 期望 |
|---|---|
| Q2 归母实际 | 79.16~79.17 亿 |
| Q2 扣非实际 | 73.73 亿 |
| Q2 营收实际 | 222.82 亿 |
| H1 归母 | 136.51 亿 |
| 交银国际净利预测 | EPS 29.119 × 11.15234641 亿股 = 340.68 亿（≈参考报告 340.7） |
| 反推 Q2（交银） | 340.68 × 39.2% − 57.35 ≈ 76.2 亿（参考报告 76.3，系数口径差异需在报告注明） |
| 归母−扣非差额 | Q2 5.42~5.44 亿 |

- [ ] **Step 3: 结构核对**

- 6 张指标卡片齐
- 预期对照 ≥ 4 家国内机构 + WebSearch 补的外资行（能搜到几家算几家，无原文剔除）
- 反推方法附录 + 数据来源明细 + 免责声明在报告尾部
- 单文件 HTML 双击可开，无外部资源引用

- [ ] **Step 4: 用户人眼验收**

浏览器打开报告，与参考图风格对照，用户确认 OK。

- [ ] **Step 5: Commit 验收产物**

```bash
cd D:/code/yeji && git add -A && git commit -m "test: 300308全流程验收报告"
```

---

### Task 9: 泛化测试（小盘股降级路径）

**Files:**
- Create: `D:\code\yeji\finreport_work\`（过程产物）

- [ ] **Step 1: 选一只机构覆盖少的股票跑全流程**

候选（研报少于 3 家的小盘股）：先跑 `fetch_forecast.py` 看 reports 数量，选一家覆盖最少的，如无研报则直接验证降级输出。

```bash
cd D:/code/yeji && python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" 002889 > finreport_work/_probe.json
python -X utf8 -c "import json; print(len(json.load(open('finreport_work/_probe.json', encoding='utf-8'))['reports']), '份研报')"
```

- [ ] **Step 2: 断言降级行为**

- 预期对照模块：机构 < 3 家时输出「无可靠预测/覆盖不足，跳过预期对照」+ 说明，**不报错不编数**
- 趋势/估值模块照常产出
- HTML 正常打开

- [ ] **Step 3: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "test: 小盘股降级路径验证"
```

---

### Task 10: 收尾（文档 + 复盘）

**Files:**
- Modify: `D:\code\yeji\docs\specs\2026-08-22-fin-report-skill-design.md`（状态行改为「已实现」）
- Create: `D:\code\yeji\README.md`

- [ ] **Step 1: 写 README.md**

`D:\code\yeji\README.md`：

```markdown
# yeji — 财报分析工作区

fin-report skill 的开发、测试与报告产出。

## 用法

任意目录对 Claude Code 说：`/fin-report 300308`（或「分析 300308 财报」）。

skill 安装位置：`C:\Users\35033\.claude\skills\fin-report\`（镜像入库于 `skill_deploy/`）。

## 结构

- `finreport/` 取数与分析纯函数库（skill 脚本依赖）
- `tests/` pytest（`-m "not net"` 可离线跑纯函数与渲染）
- `reports/`、`finreport_work/` 产物目录
- `docs/` 设计文档与实现计划

## 已知约束

- 东财 push2 系接口本机代理下不可用（skill 已绕开）
- 申万成分明细接口有 bug，同行清单走 WebSearch 人工定夺
- 外资行预测仅收录可溯源新闻稿
```

- [ ] **Step 2: 更新 spec 状态**

`docs/specs/2026-08-22-fin-report-skill-design.md` 首部「状态：待审阅」→「状态：已实现（2026-08-22）」。

- [ ] **Step 3: 全量回归**

```bash
cd D:/code/yeji && python -X utf8 -m pytest -v
```

Expected: 全部通过（net 标记测试依赖网络，失败重跑一次）。

- [ ] **Step 4: Commit**

```bash
cd D:/code/yeji && git add -A && git commit -m "docs: 收尾文档与spec状态更新"
```

---

## 验收总清单（对照 spec §8.5）

1. ✅ 300308 全流程 HTML 四模块齐全、数字与参考报告一致（Task 8）
2. ✅ 小盘股降级不报错（Task 9）
3. ✅ 反推算式、来源可查可复算（Task 8 Step 2/3）
4. ✅ 全流程数分钟内完成（Task 8 实测记录耗时）
