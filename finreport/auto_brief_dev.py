"""自动业绩快报构建：脚本量化 + 可选 AI 撰写 → 报告中心 payload。

量化部分可复现（performance.md 数值规则的代码化）：单季拆解/同比、评分卡、
反推对照（仅披露前研报）、趋势、估值、同行。驱动维定性交给 AI；
AI 缺席时该维缺省（grade_from_tones 按 warn 计 0），评级标注为量化初判。
金额约定：内部一律元（新浪源），展示层经 yi()/pct() 换算。
"""
from __future__ import annotations

import datetime as dt
import os

from .ai_summary_dev import enrich_report
from .fetch_dev import fetch_abstract_dict
from .fetch_forecast_dev import fetch_reports
from .fetch_market_dev import fetch_market
from .fetch_statements_dev import fetch_statements
from .perf_math import (
    advance_liabilities, capex_ratio, cash_coverage, four_expense_rate,
    gearing, grade_from_tones, goodwill_ratio, growth_gap,
    interest_bearing_debt, non_recurring_ratio, roe_ttm, ttm_metric,
    turnaround, yoy,
)
from .quarter_math import backcast, season_ratio, single_quarter

SEASON = {"0331": "一季报", "0630": "中报", "0930": "三季报", "1231": "年报"}
DIM_LABEL = {"growth": "成长性", "profitability": "盈利能力", "quality": "盈利质量",
             "health": "财务健康", "drivers": "业绩驱动"}
TONE_LABEL = {"good": "强", "warn": "中性", "bad": "预警"}
TONE_RANK = {"good": 0, "warn": 1, "bad": 2}


def yi(v, n: int = 2) -> str:
    return "—" if v is None else f"{v/1e8:.{n}f}"


def pct(v, n: int = 1) -> str:
    return "—" if v is None else f"{v*100:+.{n}f}%"


def prev_cum_period(period: str) -> str | None:
    """同期内上一累计期：0630→0331、0930→0630、1231→0930；0331 无。带年份。"""
    m = {"0630": "0331", "0930": "0630", "1231": "0930"}.get(period[4:])
    return period[:4] + m if m else None


def prior_year_period(period: str) -> str:
    return str(int(period[:4]) - 1) + period[4:]


# ---------- 评分卡数值规则（performance.md 通用默认阈值） ----------

def growth_tone(rev_y: float | None, np_y: float | None, turned: bool) -> str:
    if turned:
        return "warn"
    if (rev_y is not None and rev_y < 0) or (np_y is not None and np_y < 0):
        return "bad"
    if rev_y is not None and np_y is not None and rev_y >= 0.10 and np_y >= 0.10 \
            and growth_gap(np_y, rev_y) >= 0:
        return "good"
    return "warn"


def profitability_tone(mg: float | None, mg_median: float | None,
                       mg_rise: bool, roe: float | None) -> str:
    if roe is not None and roe < 0.05:
        return "bad"
    if mg is not None and mg_median is not None:
        if mg < mg_median and not mg_rise:
            return "bad"
        if mg >= mg_median and mg_rise and (roe is None or roe >= 0.10):
            return "good"
    return "warn"


def quality_tone(cov: float | None, nonrec: float | None,
                 warnings: list[str], loss: bool = False) -> str:
    # 亏损期净现比/非经常占比口径失真（分母为负），不参与打分，仅看预警
    if not loss:
        if (cov is not None and cov < 0.5) or (nonrec is not None and nonrec > 0.5):
            return "bad"
    if warnings:
        return "bad"
    if not loss and cov is not None and cov >= 0.8 and (nonrec is None or nonrec <= 0.15):
        return "good"
    return "warn"


def health_tone(gear: float | None, ibd_over_cash: float | None,
                gw_over_eq: float | None) -> str:
    if (gw_over_eq is not None and gw_over_eq >= 0.30) or \
            (ibd_over_cash is not None and ibd_over_cash > 2) or \
            (gear is not None and gear >= 0.70):
        return "bad"
    if ibd_over_cash is not None and ibd_over_cash <= 1 and \
            (gw_over_eq is None or gw_over_eq < 0.10):
        return "good"
    return "warn"


# ---------- 快报构建 ----------

def build_brief(code: str, name: str, peers: list[str] | None = None,
                use_ai: bool = True, period: str | None = None) -> dict:
    fin = fetch_abstract_dict(code)
    periods, S = fin["periods"], fin["series"]
    if period is None:
        period = periods[0]
    elif period not in periods:
        raise ValueError(f"新浪摘要未同步该期（{period}），确认后下一轮重试")
    label = f"{period[:4]} {SEASON[period[4:]]}"
    p_prev = prev_cum_period(period)
    p_py = prior_year_period(period)
    p_py_prev = prior_year_period(p_prev) if p_prev else None
    g = lambda k, p: S.get(k, {}).get(p)

    stmt = fetch_statements(code)
    I, B, C = stmt.get("income", {}), stmt.get("balance", {}), stmt.get("cashflow", {})
    announced = (stmt.get("announced") or {}).get(period, "")
    mkt = fetch_market(code, period)
    shares, price = mkt.get("total_shares"), mkt.get("price")
    mcap = shares * price if (shares and price) else None

    cum, cum_prev = g("归母净利润", period), (g("归母净利润", p_prev) if p_prev else None)
    cum_py = g("归母净利润", p_py)
    cum_py_prev = g("归母净利润", p_py_prev) if p_py_prev else None
    q2 = single_quarter(cum, cum_prev) if (cum is not None and cum_prev is not None) else cum
    q2_py = single_quarter(cum_py, cum_py_prev) if (cum_py is not None and cum_py_prev is not None) else cum_py
    np_y = yoy(q2, q2_py)
    turned = turnaround(q2, q2_py)
    rev_cum, rev_prev = g("营业总收入", period), (g("营业总收入", p_prev) if p_prev else None)
    rev_py, rev_py_prev = g("营业总收入", p_py), (g("营业总收入", p_py_prev) if p_py_prev else None)
    q2_rev = single_quarter(rev_cum, rev_prev) if (rev_cum is not None and rev_prev is not None) else rev_cum
    q2_rev_py = single_quarter(rev_py, rev_py_prev) if (rev_py is not None and rev_py_prev is not None) else rev_py
    rev_y = yoy(q2_rev, q2_rev_py)
    de_cum, de_prev = g("扣非净利润", period), (g("扣非净利润", p_prev) if p_prev else None)
    de_py, de_py_prev = g("扣非净利润", p_py), (g("扣非净利润", p_py_prev) if p_py_prev else None)
    q2_de = single_quarter(de_cum, de_prev) if (de_cum is not None and de_prev is not None) else de_cum
    q2_de_py = single_quarter(de_py, de_py_prev) if (de_py is not None and de_py_prev is not None) else de_py
    de_y = yoy(q2_de, q2_de_py)

    inc, bal, csh = I.get(period, {}), B.get(period, {}), C.get(period, {})
    bal_py = B.get(str(int(period[:4]) - 1) + "1231", {})
    mg = None
    if inc.get("营业总收入") and inc.get("营业成本") is not None:
        mg = (inc["营业总收入"] - inc["营业成本"]) / inc["营业总收入"]
    # 摘要接口毛利率为百分数值（24.43 = 24.43%），统一除 100 转小数后对比
    mg_hist = [v / 100 for v in (g("毛利率", p) for p in periods[:8]) if v is not None]
    mg_median = sorted(mg_hist)[len(mg_hist) // 2] if mg_hist else None
    mg_prev_raw = g("毛利率", p_prev) if p_prev else None
    mg_prev = mg_prev_raw / 100 if mg_prev_raw is not None else None
    annual_prior = str(int(period[:4]) - 1) + "1231"
    ttm_np = ttm_metric(cum, g("归母净利润", annual_prior), cum_py)
    equity = bal.get("归母净资产")
    roe = roe_ttm(ttm_np, equity)
    ocf, capex = csh.get("经营现金流净额"), csh.get("购建长期资产支付现金")
    cov = cash_coverage(ocf, cum)
    nonrec = non_recurring_ratio(cum, de_cum)
    ibd = interest_bearing_debt(bal.get("短期借款"), bal.get("长期借款"), bal.get("应付债券"))
    cash = bal.get("货币资金")
    ibd_over = ibd / cash if (ibd is not None and cash) else None
    gear = gearing(bal.get("负债合计"), bal.get("资产总计"))
    gw_over = goodwill_ratio(bal.get("商誉"), equity)
    rev_yoy_cum = yoy(rev_cum, rev_py)
    warnings = []
    mg_drop = mg is not None and mg_prev is not None and mg < mg_prev - 0.01
    # 增速对比预警只在营收正增长时有意义（负增长时阈值为负，形同虚设）
    if rev_yoy_cum is not None and rev_yoy_cum > 0:
        ar_cur, ar_base = bal.get("应收账款"), bal_py.get("应收账款")
        if ar_cur is not None and ar_base:
            gr = ar_cur / ar_base - 1
            if gr > rev_yoy_cum * 1.5:
                warnings.append(f"应收较年初{pct(gr)} 快于营收同比{pct(rev_yoy_cum)}×1.5，回款恶化")
        inv_cur, inv_base = bal.get("存货"), bal_py.get("存货")
        if inv_cur is not None and inv_base:
            gr = inv_cur / inv_base - 1
            if gr > rev_yoy_cum * 2 and mg_drop:
                warnings.append(f"存货较年初{pct(gr)} 高增且毛利率下行，滞销风险")
    loss = cum is not None and cum < 0

    dims = {
        "growth": {"tone": growth_tone(rev_y, np_y, turned),
                   "value": f"单季营收 {pct(rev_y)} / 归母 {pct(np_y) if np_y is not None else ('扭亏' if turned else '—')}",
                   "basis": f"单季营收 {yi(q2_rev)} 亿、归母 {yi(q2)} 亿、扣非 {yi(q2_de)} 亿（{pct(de_y)}），剪刀差 {pct(growth_gap(np_y, rev_y))}"},
        "profitability": {"tone": profitability_tone(mg, mg_median, mg_prev is None or (mg is not None and mg >= mg_prev), roe),
                          "value": f"毛利率 {pct(mg)} / ROE-TTM {pct(roe)}",
                          "basis": f"近 8 期毛利率中位数 {pct(mg_median)}；四费率 {pct(four_expense_rate(inc.get('销售费用'), inc.get('管理费用'), inc.get('研发费用'), inc.get('财务费用'), inc.get('营业总收入')), 2)}"},
        "quality": {"tone": quality_tone(cov, nonrec, warnings, loss=loss),
                    "value": f"净现比 {cov:.2f}" if cov is not None else "净现比 —",
                    "basis": ("本期亏损，净现比/非经常占比口径不适用；" if loss else "")
                             + f"OCF {yi(ocf)} 亿 vs 归母 {yi(cum)} 亿；非经常占比 {pct(nonrec)}；预警 {'、'.join(warnings) if warnings else '无'}"},
        "health": {"tone": health_tone(gear, ibd_over, gw_over),
                   "value": f"资产负债率 {pct(gear)}",
                   "basis": (f"有息负债 {yi(ibd)} 亿 / 货币资金 {yi(cash)} 亿 = {ibd_over:.2f}；"
                             f"商誉占比 {pct(gw_over)}") if ibd_over is not None else "有息负债口径缺失；商誉占比 " + pct(gw_over)},
    }

    # 反推对照（仅披露前研报，单季口径）
    fc_rows, tones_fc, eps_preds = [], [], []
    hit = miss = 0
    try:
        reports = fetch_reports(code)["reports"]
    except Exception:
        reports = []
    seen = {}
    for r in reports:
        if r["eps_2026"] is None or not announced or r["date"] >= announced:
            continue
        if r["org"] not in seen or r["date"] > seen[r["org"]]["date"]:
            seen[r["org"]] = r
    ratio_np = season_ratio(g("归母净利润", p_py), g("归母净利润", annual_prior))
    for org, r in sorted(seen.items(), key=lambda kv: kv[1]["date"], reverse=True)[:6]:
        npf = r["eps_2026"] * shares if shares else None
        bc = backcast(npf, ratio_np, cum_prev) if (npf and ratio_np is not None and cum_prev is not None and q2 is not None) else None
        if bc is None:
            continue
        diff = q2 - bc
        ok = diff >= 0 or abs(diff) / bc <= 0.02
        hit, miss = hit + ok, miss + (not ok)
        fc_rows.append([org, r["date"], r["rating"], f"{r['eps_2026']:.2f}",
                        f"{npf/1e8:.0f}", f"{bc/1e8:.1f}", f"{q2/1e8:.2f}",
                        f"{diff/1e8:+.1f} ({diff/bc*100:+.1f}%)",
                        "达标" if ok else "未达标"])
        tones_fc.append("good" if ok else "bad")
        eps_preds.append(r["eps_2026"])
    if not fc_rows:
        exp_tone = "warn"
    elif miss == 0:
        exp_tone = "good"
    else:
        exp_tone = "good" if hit > miss else "bad"

    # 估值
    vr = [["PE-TTM", f"TTM 归母 {yi(ttm_np)} 亿",
           f"{mcap/ttm_np:.1f}x" if (mcap and ttm_np) else "—",
           f"现价 {price} 元 / 市值 {yi(mcap, 0)} 亿"]]
    if eps_preds and shares and mcap:
        med = sorted(eps_preds)[len(eps_preds) // 2]
        vr.append(["PE-2026E（披露前研报中值）", f"EPS 中值 {med:.2f} 元",
                   f"{mcap/(med*shares):.1f}x",
                   f"{len(eps_preds)} 家 EPS：{'/'.join(f'{e:.2f}' for e in sorted(eps_preds))}"])

    # AI 撰写（可选；缺席则纯量化 + drivers 缺省）
    ai_used = False
    ai_full = None
    dims["drivers"] = {"tone": "warn", "value": "待 AI 定性",
                       "basis": "无 AI 模式：驱动维缺省中性（评级按四维量化初判）"}
    ai_model = os.environ.get("AI_MODEL", "deepseek-v4-flash")
    ai_note = "驱动维缺省，评级为四维量化初判。深度分析请本地运行 /fin-report " + code + "。"
    peers_source = "watchlist 配置"
    if use_ai:
        vr_med = vr[1][2] if len(vr) > 1 else "—"
        datapack = {
            "code": code, "name": name, "period": label,
            "单季": {"营收亿": yi(q2_rev), "营收同比": pct(rev_y), "归母亿": yi(q2),
                    "归母同比": pct(np_y) if np_y is not None else ("扭亏" if turned else "—"),
                    "扣非同比": pct(de_y), "毛利率": pct(mg)},
            "累计": {"营收亿": yi(rev_cum), "归母亿": yi(cum), "扣非亿": yi(de_cum),
                    "OCF亿": yi(ocf), "ROE-TTM": pct(roe)},
            "评分卡": {k: {"tone": v["tone"], "值": v["value"]} for k, v in dims.items()
                    if k != "drivers"},
            "资产负债表": {"货币资金亿": yi(cash), "有息负债亿": yi(ibd), "存货亿": yi(bal.get("存货")),
                        "应收亿": yi(bal.get("应收账款")),
                        "预收类负债亿": yi(advance_liabilities(bal.get("合同负债"), bal.get("预收款项"))),
                        "固定资产净额亿": yi(bal.get("固定资产净额")), "在建工程亿": yi(bal.get("在建工程"))},
            "非经常占比": pct(nonrec), "capex强度": capex_ratio(capex, ocf), "预警": warnings,
            "估值": {"现价": price, "市值亿": yi(mcap, 0), "PE-TTM": vr[0][2],
                    "PE-2026E研报中值": vr_med},
        }
        segs = stmt.get("segments")
        if isinstance(segs, dict) and segs:
            latest_seg = sorted(segs.keys())[-1]
            datapack["主营构成"] = {t: [{"name": x["name"], "收入亿": yi(x["revenue"]),
                                     "占比": pct(x["revenue_ratio"])}
                                    for x in items[:6]]
                                 for t, items in segs[latest_seg].items()}
        ai_full = enrich_report(datapack)
        if ai_full:
            ai_used = True
            dims["drivers"] = {"tone": ai_full["drivers"]["tone"], "value": "AI 定性",
                               "basis": ai_full["drivers"]["rationale"]}
            if not peers and ai_full["peers"]:
                peers = ai_full["peers"]
                peers_source = "AI 提名"
            ai_note = (f"summary/驱动维/前景与催化/同行提名/估值判断由 AI（{ai_model}）"
                       f"基于脚本量化数据包与行业知识生成，未经搜索溯源。深度分析请本地运行 "
                       f"/fin-report {code}。")

    tones_map = {k: v["tone"] for k, v in dims.items()}

    # 同行取数（watchlist 配置或 AI 提名，在 AI 块之后执行）
    peer_rows = []
    for pc in (peers or [])[:3]:
        try:
            pf = fetch_abstract_dict(pc)
            pm = fetch_market(pc)
            pp = pf["periods"][0]
            pn28 = pf["series"].get("归母净利润", {})
            pyt = yoy(pn28.get(pp), pn28.get(prior_year_period(pp)))
            pmg = pf["series"].get("毛利率", {}).get(pp)
            proe = pf["series"].get("净资产收益率(ROE)", {}).get(pp)
            peer_rows.append([pc, yi(pn28.get(pp)), pct(pyt),
                              pct(pmg / 100) if pmg is not None else "—",
                              pct(proe / 100) if proe is not None else "—",
                              yi(pm.get("total_shares") * pm.get("price"), 0) if (pm.get("total_shares") and pm.get("price")) else "—"])
        except Exception as exc:
            peer_rows.append([pc, "取数失败", str(exc)[:40], "—", "—", "—"])
    grade = grade_from_tones(tones_map)
    grade_label = {"A": "业绩优秀", "B": "业绩良好", "C": "业绩承压", "D": "业绩恶化"}[grade]
    grade_tone = {"A": "good", "B": "good", "C": "warn", "D": "bad"}[grade]
    summary_tone = max(grade_tone, exp_tone, key=lambda t: TONE_RANK[t])

    if ai_used:
        # tone 按合成规则可复算（performance.md），AI 只撰写文字不改判定
        summary_text = ai_full["summary"]["text"]
    else:
        ng = sum(1 for v in dims.values() if v["tone"] == "good")
        nw = sum(1 for v in dims.values() if v["tone"] == "warn")
        nb = sum(1 for v in dims.values() if v["tone"] == "bad")
        fc_txt = (f"对照 {len(fc_rows)} 家披露前机构反推：{hit} 达标、{miss} 未达标。"
                  if fc_rows else "无可溯源的披露前机构预测，预期对照跳过。")
        summary_text = (f"{name} {label}量化快报：单季归母 {yi(q2)} 亿（{pct(np_y) if np_y is not None else ('扭亏' if turned else '—')}），"
                        f"单季营收 {yi(q2_rev)} 亿（{pct(rev_y)}），毛利率 {pct(mg)}，净现比 "
                        f"{f'{cov:.2f}' if cov is not None else '—'}。评分卡 {ng}good/{nw}warn/{nb}bad，"
                        f"初判评级 {grade}（{grade_label}）。{fc_txt}")

    trend_rows = []
    for p in periods[:8]:
        lab = f"{p[:4]}{SEASON[p[4:]]}"
        # 摘要接口毛利率/ROE 为百分数值（24.43 = 24.43%），÷100 转小数后统一用 pct() 展示
        mg_p, roe_p = g("毛利率", p), g("净资产收益率(ROE)", p)
        trend_rows.append([lab, yi(g("营业总收入", p)), yi(g("归母净利润", p)),
                           yi(g("扣非净利润", p)),
                           pct(mg_p / 100) if mg_p is not None else "—",
                           pct(roe_p / 100) if roe_p is not None else "—",
                           yi(g("经营现金流量净额", p))])

    sections = [
        {"id": "scorecard", "title": "1 完整业绩判断（量化评分卡）",
         "intro": "脚本量化规则初判（references/performance.md 阈值代码化）；" + ai_note,
         "tables": [{"columns": ["维度", "名称", "本期值", "判定", "依据"],
                     "rows": [[k, DIM_LABEL[k], v["value"], TONE_LABEL[v["tone"]], v["basis"]]
                              for k, v in dims.items()],
                     "row_tones": [tones_map[k] for k in dims]}],
         "conclusion": {"tone": grade_tone,
                        "text": f"综合评级 {grade}（{grade_label}）：五维 tone {tones_map}。"
                                f"规则 good=+1/warn=0/bad=−1 求和：≥3→A、1~2→B、−2~0→C、≤−3→D。"}}]
    if ai_full:
        ol = ai_full["outlook"]
        ol_tables = []
        if ol["advantages"]:
            ol_tables.append({"columns": ["核心优势与依据（AI 推断·未经搜索溯源）"],
                              "rows": [[a] for a in ol["advantages"]], "row_tones": []})
        if ol["orders"]:
            ol_tables.append({"columns": ["订单与需求前瞻（AI 推断·未经搜索溯源）"],
                              "rows": [[ol["orders"]]], "row_tones": []})
        if ol["factors"]:
            ol_tables.append({"columns": ["影响走势因素（AI 推断·未经搜索溯源）"],
                              "rows": [[f] for f in ol["factors"]], "row_tones": []})
        if ol_tables:
            sections.append(
                {"id": "outlook", "title": f"{len(sections)+1} 前景与催化（AI 推断）",
                 "intro": "本模块由 AI 基于脚本量化数据包与行业知识生成，未经搜索溯源；"
                          "引用数字可复算，事件性表述需自行验证。",
                 "tables": ol_tables,
                 "conclusion": {"tone": tones_map.get("drivers", "warn"),
                                "text": "前瞻判断为 AI 推断口径；深度版含 WebSearch 溯源"
                                        "（本地 /fin-report）。"}})
    n = len(sections) + 1
    if fc_rows:
        sections.append(
            {"id": "expectation", "title": f"{n} 业绩 vs 机构预期（自动反推，单季口径）",
             "intro": f"披露日 {announced} 前的最新研报；反推 = EPS26E × 总股本 {shares/1e8:.2f} 亿股 × 季节系数 {pct(ratio_np)}（上年实际）− 上期累计实际。季节系数为公司历史节奏，非机构校准。",
             "tables": [{"columns": ["机构", "日期", "评级", "EPS26E", "全年净利(亿)", "反推单季(亿)", "实际单季(亿)", "差额", "判定"],
                         "rows": fc_rows, "row_tones": tones_fc}],
             "conclusion": {"tone": exp_tone,
                            "text": f"{hit}/{len(fc_rows)} 家口径达标；未达标 = 实际低于反推值超容差 2%。"}})
    else:
        sections.append(
            {"id": "expectation", "title": f"{n} 预期对照（跳过）",
             "intro": "无可溯源的披露前机构预测，预期对照降级跳过。", "tables": []})

    # ---- 纯量化深度模块（无需 AI/搜索，脚本可复算） ----
    n_sq = len(sections) + 1
    # 单季拆解：本期单季 vs 去年同期单季（累计相减）
    sq_rows = [
        ["单季营收(亿)", yi(q2_rev), yi(q2_rev_py) if q2_rev_py is not None else "—",
         pct(rev_y) if rev_y is not None else "—"],
        ["单季归母(亿)", yi(q2), yi(q2_py) if q2_py is not None else "—",
         pct(np_y) if np_y is not None else ("扭亏" if turned else "—")],
        ["单季扣非(亿)", yi(q2_de), yi(q2_de_py) if q2_de_py is not None else "—",
         pct(de_y) if de_y is not None else "—"],
    ]
    sections.append(
        {"id": "quarter", "title": f"{n_sq} 单季拆解（本期单季 vs 去年同期）",
         "intro": "单季 = 本期累计 − 上期累计；同比基期为上年同期单季。纯量化拆解，可复算。",
         "tables": [{"columns": ["指标", "本期单季", "去年同期单季", "同比"],
                     "rows": sq_rows, "row_tones": []}],
         "conclusion": {"tone": dims["growth"]["tone"],
                        "text": f"单季归母 {yi(q2)} 亿（{pct(np_y) if np_y is not None else ('扭亏' if turned else '—')}），"
                                f"扣非 {yi(q2_de)} 亿（{pct(de_y)}）；剪刀差 {pct(growth_gap(np_y, rev_y)) if (np_y is not None and rev_y is not None) else '—'}。"}})

    # 非经常损益：扣非 vs 归母、非经常占比
    nr_gap = (cum - de_cum) if (cum is not None and de_cum is not None) else None
    nr_rows = [
        ["累计归母(亿)", yi(cum)],
        ["累计扣非(亿)", yi(de_cum)],
        ["非经常损益(亿)", yi(nr_gap) if nr_gap is not None else "—"],
        ["非经常占归母比例", pct(nonrec) if nonrec is not None else "—"],
    ]
    nr_concl = ("本期归母为负，非经常占比口径失真，仅列事实。" if loss
                else (f"非经常占比 {pct(nonrec)}：" + (">50% 时利润主要靠一次性项目，可持续性弱。" if (nonrec is not None and nonrec > 0.5)
                   else "盈利主要来自主营，口径健康。" if (nonrec is not None and nonrec <= 0.15) else "介于中性区间。"))
                if nonrec is not None else "非经常占比缺失。")
    nr_tone = "bad" if (not loss and nonrec is not None and nonrec > 0.5) else ("good" if (not loss and nonrec is not None and nonrec <= 0.15) else "warn")
    sections.append(
        {"id": "nonrecurring", "title": f"{n_sq+1} 非经常损益（盈利质量）",
         "intro": "非经常损益 = 归母 − 扣非；占比高则利润依赖一次性项目。纯量化，可复算。",
         "tables": [{"columns": ["项", "金额"], "rows": nr_rows, "row_tones": []}],
         "conclusion": {"tone": nr_tone, "text": nr_concl}})

    # 主营构成（分产品/分地区，取最新累计期）
    segs = stmt.get("segments")
    seg_tables = []
    if isinstance(segs, dict) and segs:
        latest_seg = sorted(segs.keys())[-1]
        for t, items in segs[latest_seg].items():
            seg_tables.append({"columns": ["构成项", "收入(亿)", "占比", "毛利率"],
                               "rows": [[x["name"], yi(x["revenue"]),
                                         pct(x["revenue_ratio"]),
                                         pct(x["gross_margin"]) if x.get("gross_margin") is not None else "—"]
                                        for x in items[:8]],
                               "row_tones": []})
    if seg_tables:
        sections.append(
            {"id": "segments", "title": f"{n_sq+2} 主营构成（{latest_seg[:4]}年{SEASON.get(latest_seg[4:], '报告期')}）",
             "intro": "新浪主营构成，金额亿元；占比与毛利率为源数据。",
             "tables": seg_tables,
             "conclusion": {"tone": "warn", "text": "构成为最新累计期事实，结构变化需结合趋势判断。"}})

    valuation_text = ("只列倍数与基数，不构成投资建议；周期股 PE 失效场景见完整报告。")
    if ai_full and ai_full["valuation_note"]:
        valuation_text = ai_full["valuation_note"] + "（AI 判断·未经搜索溯源；不构成投资建议）"
    n2 = len(sections) + 1
    sections += [
        {"id": "trend", "title": f"{n2} 财务趋势（近 8 期累计）",
         "intro": "新浪源，金额亿元；毛利率/ROE 为累计百分数。",
         "tables": [{"columns": ["报告期", "营收", "归母", "扣非", "毛利率", "ROE累计", "经营现金流"],
                     "rows": trend_rows, "row_tones": []}],
         "conclusion": {"tone": dims["quality"]["tone"], "text": dims["quality"]["basis"]}},
        {"id": "valuation", "title": f"{n2+1} 估值（量化口径）",
         "intro": "自动报告仅列事实倍数与 AI 区间判断；行业画像调整请跑完整 skill。",
         "tables": [{"columns": ["口径", "基数", "PE", "说明"], "rows": vr, "row_tones": []}],
         "conclusion": {"tone": "warn", "text": valuation_text}}]
    if peer_rows:
        sections.append(
            {"id": "peers", "title": f"{n2+2} 同行对比（最新累计期）",
             "intro": f"同行清单来源：{peers_source}；自动取数。",
             "tables": [{"columns": ["代码", "归母(亿)", "同比", "毛利率", "ROE", "市值(亿)"],
                         "rows": peer_rows, "row_tones": []}],
             "conclusion": {"tone": "warn", "text": "同行定位为量化快照；深度对比见完整报告。"}})
    sections.append(
        {"id": "appendix", "title": "附 数据来源与自动化说明", "intro": "",
         "tables": [{"columns": ["项", "说明"],
                     "rows": [["触发", f"定时扫描检测到 {code} {label} 新披露（公告日 {announced or '未知'}）"],
                              ["财务数据", "新浪财经（akshare），脚本抓取"],
                              ["机构预测", "东财研报列表（仅披露日之前口径参与反推）"],
                              ["AI 撰写", ai_note],
                              ["同行来源", peers_source if peer_rows else "—（无配置且 AI 未提名）"],
                              ["边界", "自动化产物：无 WebSearch 溯源，AI 定性段落需自行验证；不构成投资建议，数字以公司公告为准"]],
                     "row_tones": []}],
         "notes": ["快报由 fin-report skill 的自动化管线生成，深度分析请以完整 skill 报告为准。"]})

    today = dt.date.today().isoformat()
    if ai_used:
        disclaimer = ("自动完整报告（GitHub Actions 定时扫描生成）：数字脚本可复算；"
                      "定性段落由 AI 生成、未经搜索溯源与人工复核，不构成任何投资建议。")
    else:
        disclaimer = "自动量化快报（GitHub Actions 定时扫描生成）：无 AI 撰写、无人工复核，不构成任何投资建议。"
    return {
        "meta": {"code": code, "name": name, "period_label": label, "generated": today,
                 "disclaimer": disclaimer},
        "summary": {"tone": summary_tone, "text": summary_text,
                    "links": [{"id": s["id"], "label": s["title"].split(" ", 1)[-1]}
                              for s in sections if s["id"] != "appendix"]},
        "cards": [
            {"label": "本期归母（亿）", "value": yi(cum), "tag": f"同比 {pct(yoy(cum, cum_py))}",
             "tone": dims["growth"]["tone"]},
            {"label": "单季归母（亿）", "value": yi(q2),
             "tag": f"同比 {pct(np_y) if np_y is not None else ('扭亏' if turned else '—')}",
             "tone": dims["growth"]["tone"]},
            {"label": "单季营收（亿）", "value": yi(q2_rev), "tag": f"同比 {pct(rev_y)}",
             "tone": "warn" if (rev_y is not None and rev_y < 0.10) else "good"},
            {"label": "毛利率", "value": pct(mg), "tag": "近8期中位 " + pct(mg_median),
             "tone": dims["profitability"]["tone"]},
            {"label": "净现比", "value": f"{cov:.2f}" if cov is not None else "—",
             "tag": f"OCF {yi(ocf, 1)} 亿", "tone": dims["quality"]["tone"]},
            {"label": "初判评级", "value": grade, "tag": grade_label, "tone": grade_tone},
        ],
        "sections": sections,
    }
