"""AI 撰写器：OpenAI 兼容 /v1/chat/completions（带重试与代理降级）。

环境变量：AI_API_KEY（必需，缺失即禁用）、AI_BASE_URL（缺省 https://ai.huan666.de/v1）、
AI_MODEL（缺省 deepseek-v4-flash）。调用失败一律返回 None，调用方降级为纯量化报告，
绝不阻塞流水线。纪律：AI 只允许使用脚本算好的数据包数字，行业常识可用于定性但
不得编造具体公司事件/订单/机构预测——报告中对 AI 段落显著标注「未经搜索溯源」。
"""
from __future__ import annotations

import json
import os
import time

import requests

DEFAULT_BASE = "https://ai.huan666.de/v1"
DEFAULT_MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = (
    "你是 A 股财报分析助手。纪律：1) 数字只能来自数据包，绝不编造数据包之外的"
    "机构预测、订单金额、事件；2) 行业常识可用于定性判断，但不得虚构具体公司的"
    "具体事件；3) 定性判断必须引用数据包数字作为依据；4) 输出严格 JSON，"
    "无多余文字；5) 中文。"
)


def _config() -> tuple[str | None, str, str]:
    key = os.environ.get("AI_API_KEY")
    base = os.environ.get("AI_BASE_URL", DEFAULT_BASE).rstrip("/")
    model = os.environ.get("AI_MODEL", DEFAULT_MODEL)
    return key, base, model


def chat(prompt: str, max_tokens: int = 4000, retries: int = 3) -> str | None:
    """单轮补全。网关有抖动：重试 + 退避；代理异常时直连重试。失败返回 None。"""
    key, base, model = _config()
    if not key:
        return None
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0.2,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": prompt}]}
    last_exc: Exception | None = None
    for attempt in range(retries):
        for proxies in (None, {"http": None, "https": None}):
            try:
                resp = requests.post(
                    f"{base}/chat/completions", json=body,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    timeout=120, proxies=proxies)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                if content and content.strip():
                    return content
                last_exc = ValueError("empty content")  # 网关偶发空返回，继续重试
            except Exception as exc:  # 网关抖动常见 503/SSL EOF/超时
                last_exc = exc
        time.sleep(3 * (attempt + 1))
    print(f"[ai] 调用失败（已重试 {retries} 轮）：{type(last_exc).__name__} {str(last_exc)[:120]}")
    return None


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def _tone_ok(v) -> bool:
    return v in ("good", "warn", "bad")


def enrich_report(datapack: dict) -> dict | None:
    """数据包 → 完整报告 AI 段落 | None。

    返回 {summary{text,tone}, drivers{tone,rationale},
          outlook{advantages[], orders, factors[]}, peers[6位代码], valuation_note}。
    任何 schema 不合处整体降级返回 None。
    """
    prompt = (
        "以下是脚本计算好的财报数据包（金额见字段）。请生成完整财报分析的 AI 段落，"
        "输出严格 JSON：\n"
        '{"summary": {"text": "3~4句总评：结论先行，覆盖成长/盈利/质量/健康最突出'
        '事实与最大风险", "tone": "good|warn|bad"},\n'
        ' "drivers": {"tone": "good|warn|bad", "rationale": "业绩驱动归类（需求/份额/'
        '价格/成本/一次性）与可持续性，<=60字，引用数字"},\n'
        ' "outlook": {"advantages": ["核心优势点2~3条，每条必须引用数据包数字，每条<=40字"],\n'
        '              "orders": "订单与需求前瞻1~2句：引用预收类负债/存货/主营构成'
        '数字，无相关数据则明说，<=80字",\n'
        '              "factors": ["影响股价走势因素2~3条：因素（利好/利空/中性）+理由，'
        '基于行业常识与数据包，不得编造具体事件，每条<=60字"]},\n'
        ' "peers": ["2~3家同行业可比公司A股6位代码（数字代码字符串）"],\n'
        ' "valuation_note": "估值区间位置判断1~2句：仅基于数据包中的PE与增速数字，'
        '不给买卖建议"}\n\n'
        "驱动判定参考：价格周期主导→warn；一次性损益或单一价格因素→bad；"
        "需求/份额/新业务放量且可外推→good。亏损期注意口径。\n\n数据包：\n"
        + json.dumps(datapack, ensure_ascii=False)
    )
    text = chat(prompt)
    if text is None:
        return None
    data = _extract_json(text)
    if not isinstance(data, dict):
        print(f"[ai] 返回非 JSON，降级。原始返回前 200 字：{text[:200]!r}")
        return None
    try:
        summary = data["summary"]
        drivers = data["drivers"]
        outlook = data["outlook"]
        if not _tone_ok(summary.get("tone")) or not _tone_ok(drivers.get("tone")):
            print(f"[ai] tone 非法（{summary.get('tone')!r}/{drivers.get('tone')!r}），降级")
            return None
        advantages = [str(x) for x in (outlook.get("advantages") or [])][:6]
        factors = [str(x) for x in (outlook.get("factors") or [])][:6]
        peers = [str(x).zfill(6) for x in (data.get("peers") or [])
                 if str(x).strip().isdigit()][:3]
        return {
            "summary": {"text": str(summary.get("text", ""))[:600],
                        "tone": summary["tone"]},
            "drivers": {"tone": drivers["tone"],
                        "rationale": str(drivers.get("rationale", ""))[:150]},
            "outlook": {"advantages": advantages,
                        "orders": str(outlook.get("orders", ""))[:300],
                        "factors": factors},
            "peers": peers,
            "valuation_note": str(data.get("valuation_note", ""))[:300],
        }
    except (KeyError, TypeError) as exc:
        print(f"[ai] JSON 缺字段（{exc}），降级。原始返回前 200 字：{text[:200]!r}")
        return None
