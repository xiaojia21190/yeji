"""三大报表明细 + 主营构成取数：完整业绩判断模块的数据底座。

新浪三大报表（多期，单位元）+ 东财 F10 主营构成（近两期，含收入比例与毛利率，
F10 接口非 push2 系，实测本机可用）。skill 部署时 scripts/fetch_statements.py
以薄 CLI 包装本模块。
"""
from __future__ import annotations

import akshare as ak

from .fetch_market_dev import _prefix

# 白名单映射：输出字段 → 报表内候选字段（按序取第一个存在且非空的）
INCOME_FIELDS = {
    "营业总收入": ["营业总收入", "营业收入"],
    "营业收入": ["营业收入"],
    "营业成本": ["营业成本"],
    "销售费用": ["销售费用"],
    "管理费用": ["管理费用"],
    "研发费用": ["研发费用"],
    "财务费用": ["财务费用"],
    "营业利润": ["营业利润"],
    "利润总额": ["利润总额"],
    "所得税费用": ["所得税费用"],
    "净利润": ["净利润"],
    "归母净利润": ["归属于母公司所有者的净利润"],
    "少数股东损益": ["少数股东损益"],
    "基本每股收益": ["基本每股收益"],
}
BALANCE_FIELDS = {
    "货币资金": ["货币资金"],
    "交易性金融资产": ["交易性金融资产"],
    "应收账款": ["应收账款"],
    "应收票据": ["应收票据"],
    "预付款项": ["预付款项"],
    "存货": ["存货"],
    "固定资产净额": ["固定资产净额", "固定资产净值"],
    "在建工程": ["在建工程"],
    "商誉": ["商誉"],
    "资产总计": ["资产总计"],
    "短期借款": ["短期借款"],
    "应付账款": ["应付账款"],
    "合同负债": ["合同负债"],
    "预收款项": ["预收款项"],
    "长期借款": ["长期借款"],
    "应付债券": ["应付债券"],
    "负债合计": ["负债合计"],
    "归母净资产": ["归属于母公司股东权益合计", "归属于母公司所有者权益合计"],
    "实收资本(或股本)": ["实收资本(或股本)"],
}
CASHFLOW_FIELDS = {
    "经营现金流净额": ["经营活动产生的现金流量净额"],
    "投资现金流净额": ["投资活动产生的现金流量净额"],
    "筹资现金流净额": ["筹资活动产生的现金流量净额"],
    "购建长期资产支付现金": ["购建固定资产、无形资产和其他长期资产所支付的现金"],
    "销售商品提供劳务收到现金": ["销售商品、提供劳务收到的现金"],
    "分配股利利润或偿付利息支付现金": ["分配股利、利润或偿付利息所支付的现金"],
}


def _to_float(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN -> None
    except (TypeError, ValueError):
        return None


def _normalize(df, fields: dict[str, list[str]], max_periods: int) -> dict[str, dict[str, float]]:
    """报表 df → {YYYYMMDD: {输出字段: 值}}，按报告日降序取前 max_periods 期。

    候选字段按序命中第一个非空值；全空行不输出。
    """
    if df is None or df.empty or "报告日" not in df.columns:
        return {}
    dates = sorted(df["报告日"].astype(str), reverse=True)[:max_periods]
    out: dict[str, dict[str, float]] = {}
    for date in dates:
        row = df[df["报告日"].astype(str) == date].iloc[0]
        picked: dict[str, float] = {}
        for out_name, candidates in fields.items():
            for col in candidates:
                if col in df.columns:
                    v = _to_float(row.get(col))
                    if v is not None:
                        picked[out_name] = v
                        break
        if picked:
            out[date] = picked
    return out


def _segments(code: str, max_periods: int = 2) -> dict[str, dict[str, list[dict]]]:
    """东财 F10 主营构成：{YYYYMMDD: {分类类型: [{name, revenue, revenue_ratio, gross_margin}]}}。

    单位：revenue 为元；比例与毛利率为小数。分部间抵销/小计行原样保留（负收入为抵销），
    由分析层过滤。接口异常向上抛出，由 fetch_statements 统一降级。
    """
    df = ak.stock_zygc_em(symbol=_prefix(code).upper())
    out: dict[str, dict[str, list[dict]]] = {}
    if df is None or df.empty:
        return out
    dates = sorted({str(d).replace("-", "") for d in df["报告日期"]}, reverse=True)[:max_periods]
    for date in dates:
        sub = df[df["报告日期"].astype(str).str.replace("-", "") == date]
        by_type: dict[str, list[dict]] = {}
        for ctype, rows in sub.groupby("分类类型"):
            items = []
            for _, r in rows.iterrows():
                name = str(r.get("主营构成", "")).strip()
                if not name:
                    continue
                items.append({
                    "name": name,
                    "revenue": _to_float(r.get("主营收入")),
                    "revenue_ratio": _to_float(r.get("收入比例")),
                    "gross_margin": _to_float(r.get("毛利率")),
                })
            items.sort(key=lambda x: abs(x["revenue"] or 0), reverse=True)
            if items:
                by_type[str(ctype)] = items
        if by_type:
            out[date] = by_type
    return out


def fetch_statements(code: str, max_periods: int = 10) -> dict:
    """完整业绩判断取数入口：{income, balance, cashflow, segments}。

    各报表独立降级：单表失败时对应 key 为 {"error": ...}，不阻塞其他报表。
    """
    result: dict = {}
    prefix = _prefix(code)
    for key, stmt, fields in (
        ("income", "利润表", INCOME_FIELDS),
        ("balance", "资产负债表", BALANCE_FIELDS),
        ("cashflow", "现金流量表", CASHFLOW_FIELDS),
    ):
        try:
            df = ak.stock_financial_report_sina(stock=prefix, symbol=stmt)
            result[key] = _normalize(df, fields, max_periods)
        except Exception as exc:
            result[key] = {"error": str(exc)[:200]}
    try:
        result["segments"] = _segments(code)
    except Exception as exc:
        result["segments"] = {"error": str(exc)[:200]}
    return result
