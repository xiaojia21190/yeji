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
