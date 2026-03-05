"""lint — 自动修复 .mid.md 常见书写错误。

Auto-fix common writing errors in .mid.md files.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# CJK 字符集（用于所有规则的字符类）
# CJK character set (used in all spacing rules)
# ---------------------------------------------------------------------------

# 覆盖 CJK 统一汉字、扩展 A 区；不含全角标点（全角逗号句号等不需要补空格）
# Covers CJK Unified Ideographs, Extension A; excludes fullwidth punctuation
_CJK = r"\u4e00-\u9fff\u3400-\u4dbf"

# ---------------------------------------------------------------------------
# 规则 1: MATH-BACKSLASH — 数学块内双反斜杠修复
# Rule 1: MATH-BACKSLASH — fix double backslash inside math blocks
# ---------------------------------------------------------------------------

# 匹配块级 $$...$$ 和行内 $...$ (含换行; 先处理块级避免行内规则干扰)
# Match display $$...$$ and inline $...$ (DOTALL; process display first)
_DISPLAY_MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", re.DOTALL)

# 双反斜杠后跟字母 = LaTeX 命令双写错误 (double backslash before letter)
_DOUBLE_BS_RE = re.compile(r"\\\\([a-zA-Z])")


def _fix_math_content(m: re.Match[str]) -> str:
    """Replace \\\\cmd with \\cmd inside a matched math span.

    将匹配到的数学块内 \\\\cmd 替换为 \\cmd。
    """
    return _DOUBLE_BS_RE.sub(r"\\\1", m.group(0))


def fix_math_backslash(source: str) -> str:
    """Fix double backslash LaTeX commands inside math spans.

    修复数学块内的双反斜杠 LaTeX 命令（\\\\cmd → \\cmd）。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with double backslashes inside math corrected (修正后的文本)
    """
    # 先处理块级 $$ 避免行内规则干扰 (display first to avoid inline interference)
    result = _DISPLAY_MATH_RE.sub(_fix_math_content, source)
    result = _INLINE_MATH_RE.sub(_fix_math_content, result)
    return result


# ---------------------------------------------------------------------------
# 规则 2: MATH-SPACING — 中文紧贴数学公式两侧补空格
# Rule 2: MATH-SPACING — insert space between CJK and math markers
# ---------------------------------------------------------------------------

# 行内 $（排除 $$）紧贴中文：前补空格 (CJK before inline $)
_BEFORE_INLINE_MATH_RE = re.compile(r"([" + _CJK + r"])(\$(?!\$))")
# 行内 $（排除 $$）紧贴中文：后补空格 (CJK after inline $)
_AFTER_INLINE_MATH_RE = re.compile(r"(?<!\$)(\$(?!\$))([" + _CJK + r"])")


def fix_math_spacing(source: str) -> str:
    """Insert a space between CJK characters and inline math markers.

    在中文字符与行内数学符号之间插入空格。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with spaces inserted around inline math (修正后的文本)
    """
    result = _BEFORE_INLINE_MATH_RE.sub(r"\1 \2", source)
    result = _AFTER_INLINE_MATH_RE.sub(r"\1 \2", result)
    return result


# ---------------------------------------------------------------------------
# 规则 3: BOLD-SPACING — 中文紧贴 **加重** 两侧补空格
# Rule 3: BOLD-SPACING — insert space between CJK and bold spans
# ---------------------------------------------------------------------------

# 匹配完整加重区间 **content**（内容无 * 或换行）
# Match a complete bold span **content** (no * or newline inside)
_BOLD_SPAN = r"\*\*[^*\n]+\*\*"

# 中文紧贴加重区间之前（前补空格）(CJK immediately before **span**)
_BOLD_BEFORE_CJK_RE = re.compile(r"([" + _CJK + r"])(" + _BOLD_SPAN + r")")
# 加重区间后紧贴中文（后补空格）(**span** immediately before CJK)
_BOLD_AFTER_CJK_RE = re.compile(r"(" + _BOLD_SPAN + r")([" + _CJK + r"])")


def fix_bold_spacing(source: str) -> str:
    """Insert a space between CJK characters and bold spans (**text**).

    在中文字符与完整加重区间 **text** 之间插入空格（前后两侧）。
    以整个区间为匹配单元，避免在区间内部插入空格。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with spaces inserted around bold spans (修正后的文本)
    """
    result = _BOLD_BEFORE_CJK_RE.sub(r"\1 \2", source)
    result = _BOLD_AFTER_CJK_RE.sub(r"\1 \2", result)
    return result


# ---------------------------------------------------------------------------
# 规则 4: ITALIC-SPACING — 中文紧贴 *斜体* 两侧补空格
# Rule 4: ITALIC-SPACING — insert space between CJK and italic spans
# ---------------------------------------------------------------------------

# 匹配完整斜体区间 *content*（前后均为孤立 *，不是 **；内容无 * 或换行）
# Match a complete italic span *content* (both * are lone, not **, no * or newline inside)
# (?<!\*) on the opening * prevents matching the trailing * of a ** bold closer
_ITALIC_SPAN = r"(?<!\*)\*(?!\*)[^*\n]+(?<!\*)\*(?!\*)"

# 中文紧贴斜体区间之前（前补空格）(CJK immediately before *span*)
_ITALIC_BEFORE_CJK_RE = re.compile(r"([" + _CJK + r"])(" + _ITALIC_SPAN + r")")
# 斜体区间后紧贴中文（后补空格）(*span* immediately before CJK)
_ITALIC_AFTER_CJK_RE = re.compile(r"(" + _ITALIC_SPAN + r")([" + _CJK + r"])")


def fix_italic_spacing(source: str) -> str:
    """Insert a space between CJK characters and italic spans (*text*).

    在中文字符与完整斜体区间 *text* 之间插入空格（前后两侧）。
    使用否定前/后瞻区分孤立 * 与 ** 加重标记。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with spaces inserted around italic spans (修正后的文本)
    """
    result = _ITALIC_BEFORE_CJK_RE.sub(r"\1 \2", source)
    result = _ITALIC_AFTER_CJK_RE.sub(r"\1 \2", result)
    return result


# ---------------------------------------------------------------------------
# 公共入口：按序应用所有修复 (Public entry: apply all fixes in order)
# ---------------------------------------------------------------------------
#
# 顺序说明 (Order rationale):
#   1. fix_math_backslash   — 修数学内容，不改结构
#   2. fix_math_spacing     — 数学标记周围补空格
#   3. fix_bold_spacing     — ** 周围补空格（先于 italic，防止 ** 被误识别为 *）
#   4. fix_italic_spacing   — * 周围补空格（此时 ** 已有空格，lookahead 安全）


def fix_common_errors(source: str) -> str:
    """Apply all common-error fixes in order.

    按序应用所有常见错误修复。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Fixed source text (修正后的文本)
    """
    source = fix_math_backslash(source)
    source = fix_math_spacing(source)
    source = fix_bold_spacing(source)
    source = fix_italic_spacing(source)
    return source
