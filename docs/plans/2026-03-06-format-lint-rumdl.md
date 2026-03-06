# format 命令增强：自动修复常见错误 + rumdl 格式化

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `wenqiao format` 在 wenqiao round-trip 之前，先自动修复五类常见书写错误，再通过 rumdl 进行标准 Markdown 格式化。

**Architecture:** 新增 `src/wenqiao/lint.py` 提供五个 fix 函数；`format_cmd.py` 在 round-trip 前依次调用 fix → rumdl subprocess → wenqiao round-trip；rumdl 通过 `shutil.which("rumdl")` 定位已安装二进制。

**Tech Stack:** Python 3.14, `re` (regex), `subprocess`, `shutil`, `click`, `pytest`

---

## 五类修复规则总览

| 规则 | 问题 | 修复 |
|------|------|------|
| **MATH-BACKSLASH** | 数学块内 `\\cmd` | → `\cmd` |
| **MATH-SPACING** | 中文紧贴 `$` | 两侧插空格 |
| **BOLD-SPACING** | 中文紧贴 `**...**` | 两侧插空格 |
| **ITALIC-SPACING** | 中文紧贴 `*...*` | 两侧插空格 |
| **BOLD-COLLISION** | `**text**` 后紧跟非空白非标点 | 插空格（BOLD-SPACING after 的超集，保留语义独立） |

> BOLD-SPACING 同时处理前后，ITALIC-SPACING 同理。中文字符范围：`\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef`。

---

## 规则示例

```
# MATH-BACKSLASH
$\\mathbf{R}$      →  $\mathbf{R}$
$$\\frac{1}{2}$$   →  $$\frac{1}{2}$$

# MATH-SPACING（前后均补空格）
这是$x^2$公式      →  这是 $x^2$ 公式
公式$\alpha$和     →  公式 $\alpha$ 和

# BOLD-SPACING（前后均补空格）
关键**概念**在这里  →  关键 **概念** 在这里
这里**重要**结论    →  这里 **重要** 结论

# ITALIC-SPACING（前后均补空格）
见*图1*所示        →  见 *图1* 所示
*注意*这一点       →  *注意* 这一点

# BOLD-COLLISION（后面紧跟任意非空白非标点）
**注意**这         →  **注意** 这    （已被 BOLD-SPACING after 覆盖）
```

---

## Task 1：新建 `src/wenqiao/lint.py`

**Files:**
- Create: `src/wenqiao/lint.py`

### Step 1: 验证模块尚不存在

运行：`uv run python -c "from wenqiao.lint import fix_common_errors"`
预期：`ModuleNotFoundError`

### Step 2: 创建 `src/wenqiao/lint.py`

```python
"""lint — 自动修复 .mid.md 常见书写错误。

Auto-fix common writing errors in .mid.md files.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# CJK 字符集（用于所有规则的字符类）
# CJK character set (used in all spacing rules)
# ---------------------------------------------------------------------------

# 覆盖 CJK 统一汉字、扩展 A 区、全角字符
# Covers CJK Unified Ideographs, Extension A, Halfwidth/Fullwidth Forms
_CJK = r"\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef"

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
_AFTER_INLINE_MATH_RE = re.compile(r"(\$(?!\$))([" + _CJK + r"])")


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
# Rule 3: BOLD-SPACING — insert space between CJK and bold markers
# ---------------------------------------------------------------------------

# 中文紧贴开 ** 之前 (CJK before opening **)
_BEFORE_BOLD_RE = re.compile(r"([" + _CJK + r"])(\*\*)")
# ** 后紧贴中文或字母数字 (** followed immediately by CJK or alphanumeric)
_AFTER_BOLD_RE = re.compile(r"(\*\*)([" + _CJK + r"a-zA-Z0-9])")


def fix_bold_spacing(source: str) -> str:
    """Insert a space between CJK characters and bold markers (**).

    在中文字符与加重标记 ** 之间插入空格（前后两侧）。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with spaces inserted around bold markers (修正后的文本)
    """
    result = _BEFORE_BOLD_RE.sub(r"\1 \2", source)
    result = _AFTER_BOLD_RE.sub(r"\1 \2", result)
    return result


# ---------------------------------------------------------------------------
# 规则 4: ITALIC-SPACING — 中文紧贴 *斜体* 两侧补空格
# Rule 4: ITALIC-SPACING — insert space between CJK and italic markers
# ---------------------------------------------------------------------------

# 中文紧贴单 *（不是 **）之前 (CJK before lone *, not part of **)
_BEFORE_ITALIC_RE = re.compile(r"([" + _CJK + r"])(\*(?!\*))")
# 单 *（不是 **）后紧贴中文 (lone * followed immediately by CJK)
_AFTER_ITALIC_RE = re.compile(r"(?<!\*)(\*)([" + _CJK + r"])")


def fix_italic_spacing(source: str) -> str:
    """Insert a space between CJK characters and italic markers (*).

    在中文字符与斜体标记 * 之间插入空格（前后两侧）。
    使用否定前/后瞻确保不误匹配 ** 内的 *。

    Args:
        source: Raw .mid.md source text (原始 .mid.md 源文本)

    Returns:
        Source with spaces inserted around italic markers (修正后的文本)
    """
    result = _BEFORE_ITALIC_RE.sub(r"\1 \2", source)
    result = _AFTER_ITALIC_RE.sub(r"\1 \2", result)
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
```

### Step 3: 确认模块可导入

运行：`uv run python -c "from wenqiao.lint import fix_common_errors; print('ok')"`
预期：`ok`

---

## Task 2：编写 `tests/test_lint.py`

**Files:**
- Create: `tests/test_lint.py`

### Step 1: 创建测试文件

```python
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
    # No extra space injected between the two $ signs
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
    """Bold followed by punctuation is not changed (后跟标点不修改)."""
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
    assert "公式 $" in result           # MATH-SPACING before
    assert "$ **" in result             # MATH-SPACING after + BOLD before
    assert "** 这" in result            # BOLD after
    assert "* 图" in result             # ITALIC after


def test_fix_common_errors_idempotent() -> None:
    """Applying fix_common_errors twice gives the same result (幂等性)."""
    src = r"$\\alpha$**加重**文字*斜体*内容"
    once = fix_common_errors(src)
    twice = fix_common_errors(once)
    assert once == twice
```

### Step 2: 运行测试

运行：`uv run pytest tests/test_lint.py -v`
预期：全部 PASSED

若有失败，检查对应规则的正则是否正确，调整 `lint.py` 直到全绿。

---

## Task 3：修改 `src/wenqiao/format_cmd.py`

**Files:**
- Modify: `src/wenqiao/format_cmd.py`

### Step 1: 先写针对 format 集成的失败测试

在 `tests/test_format.py` 末尾追加：

```python
def test_format_fixes_math_backslash(tmp_path: Path) -> None:
    """format auto-fixes double backslash in math (自动修复数学双反斜杠)."""
    src = tmp_path / "doc.mid.md"
    src.write_text(r"# 标题" + "\n\n" + r"公式 $\\mathbf{R}$ 在这里。" + "\n")
    result = CliRunner().invoke(main, ["format", str(src)])
    assert result.exit_code == 0
    content = src.read_text()
    assert r"$\mathbf{R}$" in content
    assert r"$\\mathbf{R}$" not in content


def test_format_fixes_math_spacing(tmp_path: Path) -> None:
    """format auto-fixes missing spaces around math (自动修复数学公式两侧空格)."""
    src = tmp_path / "doc.mid.md"
    src.write_text("# 标题\n\n这是$x^2$公式。\n")
    result = CliRunner().invoke(main, ["format", str(src)])
    assert result.exit_code == 0
    content = src.read_text()
    assert "这是 $x^2$ 公式" in content


def test_format_fixes_bold_spacing(tmp_path: Path) -> None:
    """format auto-fixes bold marker spacing (自动修复加重标记两侧空格)."""
    src = tmp_path / "doc.mid.md"
    src.write_text("# 标题\n\n这是**重要**结论。\n")
    result = CliRunner().invoke(main, ["format", str(src)])
    assert result.exit_code == 0
    content = src.read_text()
    assert "这是 **重要** 结论" in content


def test_format_no_rumdl_flag(tmp_path: Path) -> None:
    """--no-rumdl skips rumdl step without error (--no-rumdl 跳过 rumdl 无报错)."""
    src = tmp_path / "doc.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    result = CliRunner().invoke(main, ["format", str(src), "--no-rumdl"])
    assert result.exit_code == 0
```

运行：`uv run pytest tests/test_format.py::test_format_fixes_math_backslash -v`
预期：FAIL（format_cmd.py 尚未调用 fix_common_errors）

### Step 2: 完整替换 `format_cmd.py`

```python
"""format 子命令：规范化学术 Markdown 源文件。

Format subcommand: normalize academic Markdown source files.
Pipeline: fix common errors → rumdl → wenqiao round-trip.
"""

from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from wenqiao.diagnostic import DiagCollector
from wenqiao.lint import fix_common_errors
from wenqiao.markdown import MarkdownRenderer
from wenqiao.pipeline import parse_and_process


def _run_rumdl(text: str) -> str:
    """Run rumdl --fix on text, return fixed text.

    通过 rumdl --fix 格式化文本并返回结果。
    若 rumdl 不可用则原样返回并打印警告。

    Args:
        text: Markdown source text (Markdown 源文本)

    Returns:
        rumdl-formatted text, or original if rumdl unavailable
        (rumdl 格式化后的文本；rumdl 不可用时返回原文)
    """
    # 优先从 PATH 查找；回退到 venv bin 目录 (PATH first, then venv bin dir)
    rumdl_bin = shutil.which("rumdl")
    if rumdl_bin is None:
        candidate = Path(sys.executable).parent / "rumdl"
        if candidate.exists():
            rumdl_bin = str(candidate)

    if rumdl_bin is None:
        click.echo(
            "[format] rumdl not found; skipping. "
            "Install with: uv add rumdl (rumdl 未找到，跳过该步骤)",
            err=True,
        )
        return text

    # 写临时文件 → rumdl 原地修改 → 读回 → 删除 (write → fix in-place → read → delete)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        # rumdl --fix 在修改了文件时以非零退出；check=False 忽略退出码
        # rumdl --fix exits non-zero when it makes changes; check=False ignores that
        subprocess.run(
            [rumdl_bin, "--fix", str(tmp_path)],
            check=False,
            capture_output=True,
        )
        return tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)


@click.command("format")
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path (输出路径; default: overwrite input file)",
)
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Check if file is formatted, exit 1 if not (检查格式化状态，未格式化时退出码 1)",
)
@click.option(
    "--diff",
    "show_diff",
    is_flag=True,
    default=False,
    help="Show unified diff of changes (显示统一差异)",
)
@click.option(
    "--no-rumdl",
    "skip_rumdl",
    is_flag=True,
    default=False,
    help="Skip rumdl formatting step (跳过 rumdl 格式化步骤)",
)
def format_cmd(
    input: Path,
    output: Path | None,
    check: bool,
    show_diff: bool,
    skip_rumdl: bool,
) -> None:
    """Format an academic Markdown file (格式化学术 Markdown 文件).

    Pipeline: fix common errors → rumdl fmt → wenqiao round-trip.
    流水线：修复常见错误 → rumdl 格式化 → wenqiao 往返规范化。
    """
    original = input.read_text(encoding="utf-8")
    filename = str(input)

    # 步骤 1: 修复常见错误（数学双反斜杠、数学/加重/斜体空格）
    # Step 1: fix common errors (math backslash, math/bold/italic spacing)
    text = fix_common_errors(original)

    # 步骤 2: rumdl 格式化（可跳过）
    # Step 2: rumdl formatting (optional)
    if not skip_rumdl:
        text = _run_rumdl(text)

    # 步骤 3: wenqiao round-trip（解析 → 处理注释 → 渲染）
    # Step 3: wenqiao round-trip (parse → process comments → render)
    diag = DiagCollector(filename)
    east = parse_and_process(text, filename, diag)
    renderer = MarkdownRenderer(mode="full", diag=diag)
    formatted = renderer.render(east)

    # 比较原文与格式化结果 (Compare original and formatted)
    is_clean = original == formatted

    # 按需显示差异 (Show diff if requested)
    if show_diff and not is_clean:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            formatted.splitlines(keepends=True),
            fromfile=f"a/{input.name}",
            tofile=f"b/{input.name}",
        )
        sys.stdout.writelines(diff)

    # 检查模式 (Check mode)
    if check:
        if is_clean:
            click.echo(f"{input}: ok", err=True)
        else:
            click.echo(f"{input}: needs formatting (需要格式化)", err=True)
            raise SystemExit(1)
        return

    # 写入输出 (Write output)
    target = output if output is not None else input
    target.write_text(formatted, encoding="utf-8")
    click.echo(f"Formatted {target}")
```

### Step 3: 运行全部 format 测试

运行：`uv run pytest tests/test_format.py -v`
预期：全部 PASSED

### Step 4: 运行全套检查

运行：`make test`
预期：全部 PASSED，无回归

### Step 5: Commit

```bash
git add src/wenqiao/lint.py tests/test_lint.py src/wenqiao/format_cmd.py tests/test_format.py
git commit -m "feat(format): fix math/bold/italic spacing, math backslash, integrate rumdl"
```

---

## 注意事项

### Italic 规则与 Bold 的交互

处理顺序为先 `fix_bold_spacing`（处理 `**`），再 `fix_italic_spacing`（处理孤立 `*`）。
italic 规则使用 `(?<!\*)` 和 `(?!\*)` 确保不误匹配 `**` 内的 `*`。

### rumdl 退出码

`rumdl --fix file` 在修改了文件时返回非零退出码，属正常行为，使用 `check=False`。

### Display math 的 `$$` 不被行内规则误改

`_BEFORE_INLINE_MATH_RE` 使用 `\$(?!\$)` — 即 `$` 后面不跟 `$` — 避免匹配 `$$` 中的第一个 `$`。同理 `_AFTER_INLINE_MATH_RE` 使用 `(?<!\$)\$` — 前面不是 `$`。
