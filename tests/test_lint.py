"""lint 模块的单元测试。

Unit tests for the lint auto-fix module.
"""

from __future__ import annotations

from wenqiao.lint import (
    fix_bold_spacing,
    fix_common_errors,
    fix_italic_spacing,
    fix_math_backslash,
    fix_math_spacing,
)


# ---------------------------------------------------------------------------
# fix_math_backslash
# ---------------------------------------------------------------------------


def test_fix_math_backslash_inline() -> None:
    """Inline math double backslash is corrected (行内数学双反斜杠被修正)."""
    src = r"公式 $\\mathbf{R}$ 在这里。"
    assert r"$\mathbf{R}$" in fix_math_backslash(src)
    assert r"$\\mathbf{R}$" not in fix_math_backslash(src)


def test_fix_math_backslash_display() -> None:
    """Display math double backslash is corrected (块级数学双反斜杠被修正)."""
    src = r"$$\\frac{1}{2}$$"
    result = fix_math_backslash(src)
    assert r"$$\frac{1}{2}$$" in result
    assert r"$$\\frac" not in result


def test_fix_math_backslash_no_change_outside_math() -> None:
    """Double backslash outside math is left untouched (数学块外不修改)."""
    src = r"普通文本 \\n 换行符"
    assert fix_math_backslash(src) == src


def test_fix_math_backslash_correct_already() -> None:
    """Correctly written math is not changed (已正确的不修改)."""
    src = r"公式 $\mathbf{R} \in SO(3)$ 无问题。"
    assert fix_math_backslash(src) == src


def test_fix_math_backslash_multiple_spans() -> None:
    """Multiple math spans in one line are all fixed (多个数学块均被修正)."""
    src = r"$\\alpha$ 和 $\\beta$"
    result = fix_math_backslash(src)
    assert r"$\alpha$" in result
    assert r"$\beta$" in result


# ---------------------------------------------------------------------------
# fix_math_spacing
# ---------------------------------------------------------------------------


def test_fix_math_spacing_before() -> None:
    """CJK immediately before $ gets a space (中文前补空格)."""
    assert "这是 $x^2$" in fix_math_spacing("这是$x^2$")


def test_fix_math_spacing_after() -> None:
    """CJK immediately after $ gets a space (中文后补空格)."""
    assert "$x^2$ 公式" in fix_math_spacing("$x^2$公式")


def test_fix_math_spacing_both_sides() -> None:
    """CJK on both sides of inline math both get spaces (两侧均补空格)."""
    result = fix_math_spacing("这是$x$公式")
    assert "这是 $x$ 公式" in result


def test_fix_math_spacing_no_change_when_spaced() -> None:
    """Already-spaced math is not changed (已有空格的不修改)."""
    src = "这是 $x^2$ 公式。"
    assert fix_math_spacing(src) == src


def test_fix_math_spacing_display_math_untouched() -> None:
    """Display $$ markers are not double-spaced by inline rule (块级 $$ 不被误匹配)."""
    src = "$$x^2$$"
    result = fix_math_spacing(src)
    # No extra space injected between the two $ signs (不在两个 $ 号之间插入空格)
    assert "$ $" not in result


# ---------------------------------------------------------------------------
# fix_bold_spacing
# ---------------------------------------------------------------------------


def test_fix_bold_spacing_after_cjk() -> None:
    """CJK before ** gets a space (中文前补空格)."""
    assert "关键 **概念**" in fix_bold_spacing("关键**概念**")


def test_fix_bold_spacing_before_cjk() -> None:
    """CJK after ** gets a space (中文后补空格)."""
    assert "**概念** 在" in fix_bold_spacing("**概念**在")


def test_fix_bold_spacing_both_sides() -> None:
    """CJK on both sides of bold both get spaces (两侧均补空格)."""
    result = fix_bold_spacing("这是**重要**结论")
    assert "这是 **重要** 结论" in result


def test_fix_bold_spacing_no_change_when_spaced() -> None:
    """Already-spaced bold is not changed (已有空格的不修改)."""
    src = "这是 **重要** 结论。"
    assert fix_bold_spacing(src) == src


def test_fix_bold_spacing_followed_by_punctuation() -> None:
    """Bold followed by CJK punctuation is not changed (后跟中文标点不修改)."""
    src = "**重要**，这一点"
    assert fix_bold_spacing(src) == src


# ---------------------------------------------------------------------------
# fix_italic_spacing
# ---------------------------------------------------------------------------


def test_fix_italic_spacing_after_cjk() -> None:
    """CJK before * (italic) gets a space (中文前补空格)."""
    assert "见 *图1*" in fix_italic_spacing("见*图1*")


def test_fix_italic_spacing_before_cjk() -> None:
    """CJK after * (italic) gets a space (中文后补空格)."""
    assert "*注意* 这" in fix_italic_spacing("*注意*这")


def test_fix_italic_spacing_does_not_affect_bold() -> None:
    """Bold markers ** are not modified by italic rule (不误改 ** 加重标记)."""
    src = "**重要** 结论"
    result = fix_italic_spacing(src)
    assert result == src


def test_fix_italic_spacing_no_change_when_spaced() -> None:
    """Already-spaced italic is not changed (已有空格的不修改)."""
    src = "见 *图1* 所示。"
    assert fix_italic_spacing(src) == src


# ---------------------------------------------------------------------------
# fix_common_errors — 集成 + 幂等性 (integration + idempotency)
# ---------------------------------------------------------------------------


def test_fix_common_errors_applies_all() -> None:
    """fix_common_errors applies all four fixes (依序应用四种修复)."""
    src = r"公式$\\mathbf{R}$**注意**这点*见*图"
    result = fix_common_errors(src)
    assert r"$\mathbf{R}$" in result   # MATH-BACKSLASH
    assert "公式 $" in result           # MATH-SPACING before (CJK before $)
    assert "** 这" in result            # BOLD-SPACING after (**注意** before 这)
    assert "* 图" in result             # ITALIC-SPACING after (*见* before 图)


def test_fix_common_errors_idempotent() -> None:
    """Applying fix_common_errors twice gives the same result (幂等性)."""
    src = r"$\\alpha$**加重**文字*斜体*内容"
    once = fix_common_errors(src)
    twice = fix_common_errors(once)
    assert once == twice
