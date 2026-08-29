"""完整业绩判断核心算式：增速、TTM、含金量、财务健康、五维评分卡合成。

金额单位约定：函数入参/返回值一律为「元」（与 akshare 新浪源一致）；
增速/比率类一律返回小数（0.24 表示 24%）；输入缺失（None）或分母为 0
时返回 None，由展示层判空，不在算式内造默认值。
"""
from __future__ import annotations

# 五维评分卡的维度 key（payload 与 references/performance.md 的标准名）
DIMENSIONS = ("growth", "profitability", "quality", "health", "drivers")

# 综合评级 → 展示文案
VERDICT_LABEL = {"A": "业绩优秀", "B": "业绩良好", "C": "业绩承压", "D": "业绩恶化"}

_TONE_SCORE = {"good": 1, "warn": 0, "bad": -1}


def yoy(curr: float | None, prev: float | None) -> float | None:
    """同比增速（小数）。基期缺失/为 0/为负时返回 None——负基数增速无意义，
    扭亏情形用 turnaround() 单独表述。"""
    if curr is None or prev is None or prev <= 0:
        return None
    return curr / prev - 1


def turnaround(curr: float | None, prev: float | None) -> bool:
    """扭亏为盈：基期为负且当期为正。"""
    return curr is not None and prev is not None and prev < 0 < curr


def growth_gap(profit_yoy: float | None, revenue_yoy: float | None) -> float | None:
    """增速剪刀差：归母净利同比 − 营收同比（小数）。正值 = 利润跑赢营收。"""
    if profit_yoy is None or revenue_yoy is None:
        return None
    return profit_yoy - revenue_yoy


def ttm_metric(latest_cum: float | None, annual_prior: float | None,
               cum_prior_same_period: float | None) -> float | None:
    """滚动十二期值 = 上年年报 + 本期累计 − 上年同期累计。任一缺失返回 None。"""
    if latest_cum is None or annual_prior is None or cum_prior_same_period is None:
        return None
    return annual_prior + latest_cum - cum_prior_same_period


def roe_ttm(ttm_profit: float | None, equity: float | None) -> float | None:
    """ROE-TTM（小数）= TTM 归母净利 / 期末归母净资产。"""
    if not ttm_profit or not equity:
        return None
    return ttm_profit / equity


def cash_coverage(ocf: float | None, net_profit: float | None) -> float | None:
    """净现比 = 经营现金流净额 / 归母净利。净利为 0/缺失返回 None。"""
    if ocf is None or not net_profit:
        return None
    return ocf / net_profit


def fcf(ocf: float | None, capex: float | None) -> float | None:
    """简易自由现金流 = 经营现金流净额 − 购建长期资产支付的现金。"""
    if ocf is None or capex is None:
        return None
    return ocf - capex


def capex_ratio(capex: float | None, ocf: float | None) -> float | None:
    """资本开支强度 = 购建长期资产支付现金 / 经营现金流净额。>1 = 投资期透支经营现金。"""
    if capex is None or not ocf:
        return None
    return capex / ocf


def expense_ratio(expense: float | None, revenue: float | None) -> float | None:
    """费用率（小数）= 费用 / 营业总收入。"""
    if expense is None or not revenue:
        return None
    return expense / revenue


def four_expense_rate(selling: float | None, admin: float | None, rd: float | None,
                      finance: float | None, revenue: float | None) -> float | None:
    """四费费率（小数）=（销售+管理+研发+财务费用）/ 营业总收入。缺失项按 0 计。"""
    if not revenue:
        return None
    total = sum(v for v in (selling, admin, rd, finance) if v is not None)
    return total / revenue


def interest_bearing_debt(short_loan: float | None, long_loan: float | None,
                          bonds: float | None) -> float | None:
    """有息负债 = 短期借款 + 长期借款 + 应付债券。三项全缺失返回 None。"""
    vals = (short_loan, long_loan, bonds)
    if all(v is None for v in vals):
        return None
    return sum(v for v in vals if v is not None)


def advance_liabilities(contract_liab: float | None,
                        prepaid: float | None) -> float | None:
    """预收款类负债 = 合同负债 + 预收款项（新准则用前者，旧准则用后者）。
    两项全缺失返回 None，缺失项按 0 计。"""
    if contract_liab is None and prepaid is None:
        return None
    return (contract_liab or 0) + (prepaid or 0)


def advance_ratio(advance: float | None, revenue: float | None) -> float | None:
    """订单前置强度（小数）= 预收款类负债 / 营业总收入。
    抬升 = 在手订单前置信号；to B 长账期行业此值天然小，仅作辅助。"""
    if advance is None or not revenue:
        return None
    return advance / revenue


def gearing(total_liab: float | None, total_assets: float | None) -> float | None:
    """资产负债率（小数）= 负债合计 / 资产总计。"""
    if total_liab is None or not total_assets:
        return None
    return total_liab / total_assets


def goodwill_ratio(goodwill: float | None, equity: float | None) -> float | None:
    """商誉占归母净资产比（小数）。"""
    if goodwill is None or not equity:
        return None
    return goodwill / equity


def non_recurring_ratio(net_profit: float | None, deducted: float | None) -> float | None:
    """非经常性损益占归母比重（小数）= 1 − 扣非净利润 / 归母净利润。"""
    if not net_profit or deducted is None:
        return None
    return 1 - deducted / net_profit


def grade_from_tones(tones: dict[str, str]) -> str:
    """五维 tone → 综合评级 A/B/C/D。

    计分 good=+1 / warn=0 / bad=-1（缺失维度按 warn 计 0）：
    sum ≥ 3 → A；1~2 → B；−2~0 → C；≤ −3 → D。
    覆盖规则：成长性与盈利质量同为 bad → 至多 C（增长失速叠加含金量差，
    不允许落到良好档，与 performance.md 的合成规则一致）。
    """
    score = sum(_TONE_SCORE.get(tones.get(d, "warn"), 0) for d in DIMENSIONS)
    if score >= 3:
        grade = "A"
    elif score >= 1:
        grade = "B"
    elif score >= -2:
        grade = "C"
    else:
        grade = "D"
    if grade in ("A", "B") and tones.get("growth") == "bad" and tones.get("quality") == "bad":
        grade = "C"
    return grade
