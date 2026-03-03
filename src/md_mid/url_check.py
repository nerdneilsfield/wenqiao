"""Shared URL safety utilities for scheme validation.

跨模块共享的 URL 安全检查工具，用于 scheme 校验。
"""

from __future__ import annotations

import re

# Strip ASCII control characters from URLs before scheme check
# (URL 中 ASCII 控制字符清除)
_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# Dangerous URI schemes to block (危险 URI scheme 黑名单)
_UNSAFE_SCHEMES = (
    "javascript:",
    "vbscript:",
    "data:text/html",
    "data:image/svg+xml",
)


def is_unsafe_url(url: str) -> bool:
    """Check whether a URL uses a dangerous scheme.

    检查 URL 是否使用危险的 scheme。

    Strips control characters and whitespace before checking to prevent
    bypass via embedded tabs/newlines (先清除控制字符和空白再检查，防止绕过).

    Args:
        url: The URL string to validate (待校验的 URL 字符串)

    Returns:
        True if URL uses a blocked scheme (URL 使用被阻止的 scheme 时返回 True)
    """
    cleaned = _CTRL_CHARS_RE.sub("", url).strip().lower()
    return cleaned.startswith(_UNSAFE_SCHEMES)
