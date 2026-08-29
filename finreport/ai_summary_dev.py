"""AI 撰写器：OpenAI 兼容 /v1/chat/completions（带重试与代理降级）。

环境变量：AI_API_KEY（必需，缺失即禁用）、AI_BASE_URL（缺省 https://ai.huan666.de/v1）、
AI_MODEL（缺省 deepseek-v4-flash）。调用失败一律返回 None，调用方降级为纯量化快报，
绝不阻塞流水线。纪律：AI 只允许使用脚本算好的数据包数字，不得编造外部信息。
"""
from __future__ import annotations

import json
import os
import time

import requests

DEFAULT_BASE = "https://ai.huan666.de/v1"
DEFAULT_MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = (
    "你是 A 股财报分析助手。纪律：1) 只使用数据包中给出的数字，"
    "绝不编造数据包之外的机构预测、产量、订单、事件等信息；"
    "2) 定性判断必须引用数据包数字作为依据；3) 输出严格 JSON，无多余文字；4) 中文。"
)


def _config() -> tuple[str | None, str, str]:
    key = os.environ.get("AI_API_KEY")
    base = os.environ.get("AI_BASE_URL", DEFAULT_BASE).rstrip("/")
    model = os.environ.get("AI_MODEL", DEFAULT_MODEL)
    return key, base, model


def chat(prompt: str, max_tokens: int = 1500, retries: int = 3) -> str | None:
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
                    timeout=90, proxies=proxies)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as exc:  # 网关抖动常见 503/SSL EOF/超时
                last_exc = exc
        time.sleep(3 * (attempt + 1))
    print(f"[ai] 调用失败（已重试 {retries} 轮）：{type(last_exc).__name__} {str(last_exc)[:120]}")
    return None


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def enrich_brief(datapack: dict) -> dict | None:
    """数据包 → {summary:{text,tone}, drivers:{tone,rationale}} | None。

    summary 3~4 句事实（不构成投资建议）；drivers tone ∈ good/warn/bad，
    rationale ≤60 字且必须引用数据包数字。
    """
    prompt = (
        "以下是脚本计算好的财报数据包（单位见字段）。请输出严格 JSON：\n"
        '{"summary": {"text": "3~4句总评：第一句给关键结论，涵盖成长/盈利/质量/健康的'
        '最突出事实与最大风险", "tone": "good|warn|bad"}, '
        '"drivers": {"tone": "good|warn|bad", "rationale": "业绩驱动归类（需求/份额/价格/'
        '成本/一次性）与可持续性，<=60字，必须引用数字"}}\n\n'
        "驱动判定参考：价格周期主导→warn；一次性损益或单一价格因素→bad；"
        "需求/份额/新业务放量驱动且可外推→good。\n\n数据包：\n"
        + json.dumps(datapack, ensure_ascii=False)
    )
    text = chat(prompt)
    if text is None:
        return None
    data = _extract_json(text)
    if not data or "summary" not in data or "drivers" not in data:
        print(f"[ai] 返回 JSON 不合 schema，降级纯量化。原始返回前 200 字：{text[:200]!r}")
        return None
    tone = data["summary"].get("tone")
    dtone = data["drivers"].get("tone")
    if tone not in ("good", "warn", "bad") or dtone not in ("good", "warn", "bad"):
        print(f"[ai] tone 非法（summary={tone!r} drivers={dtone!r}），降级纯量化")
        return None
    return {"summary": {"text": str(data["summary"].get("text", ""))[:500], "tone": tone},
            "drivers": {"tone": dtone,
                        "rationale": str(data["drivers"].get("rationale", ""))[:120]}}
