"""format 子命令：规范化学术 Markdown 源文件。

Format subcommand: normalize academic Markdown source files.
Pipeline: fix common errors → optional rumdl.
流水线：修复常见错误 → 可选 rumdl 格式化。
"""

from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

import click

from wenqiao.diagnostic import DiagCollector
from wenqiao.lint import fix_common_errors
from wenqiao.markdown import MarkdownRenderer
from wenqiao.pipeline import parse_and_process

_MID_MARKERS = (
    "(cite:",
    "(ref:",
    "<!-- label:",
    "<!-- caption:",
    "<!-- ai-generated:",
    "<!-- ai-prompt:",
    "<!-- begin:",
    "<!-- end:",
)


def _looks_like_mid(text: str) -> bool:
    """Heuristic: detect wenqiao-specific .mid.md syntax."""
    return any(marker in text for marker in _MID_MARKERS)


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


def _format_signed(n: int) -> str:
    """Format signed integer for human-readable stats output."""
    return f"+{n}" if n >= 0 else str(n)


def _compute_line_change_stats(before: str, after: str) -> tuple[int, int, int]:
    """Compute changed blocks and +/- line counts.

    Returns:
        (changed_blocks, added_lines, removed_lines)
    """
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = SequenceMatcher(a=before_lines, b=after_lines)
    changed_blocks = 0
    added = 0
    removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed_blocks += 1
        if tag in ("insert", "replace"):
            added += j2 - j1
        if tag in ("delete", "replace"):
            removed += i2 - i1
    return changed_blocks, added, removed


def _emit_stats(before: str, after: str, *, target: Path, changed: bool) -> None:
    """Print formatting stats (输出格式化统计信息)."""
    before_lines = len(before.splitlines())
    after_lines = len(after.splitlines())
    before_chars = len(before)
    after_chars = len(after)
    blocks, added, removed = _compute_line_change_stats(before, after)
    delta_lines = after_lines - before_lines
    delta_chars = after_chars - before_chars

    click.echo(
        "[format] Stats "
        f"file={target} changed={str(changed).lower()} "
        f"lines={before_lines}->{after_lines} ({_format_signed(delta_lines)}) "
        f"chars={before_chars}->{after_chars} ({_format_signed(delta_chars)}) "
        f"diff=+{added}/-{removed} blocks={blocks}",
        err=True,
    )


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
@click.option(
    "--stats",
    "show_stats",
    is_flag=True,
    default=False,
    help="Show formatting statistics (显示格式化统计信息)",
)
def format_cmd(
    input: Path,
    output: Path | None,
    check: bool,
    show_diff: bool,
    skip_rumdl: bool,
    show_stats: bool,
) -> None:
    """Format an academic Markdown file (格式化学术 Markdown 文件).

    Pipeline: fix common errors → optional rumdl.
    流水线：修复常见错误 → 可选 rumdl 格式化。
    """
    original = input.read_text(encoding="utf-8")

    is_mid = _looks_like_mid(original)

    # 步骤 1: 修复常见错误（数学双反斜杠、数学/加重/斜体间距）
    # Step 1: fix common errors (math backslash, math/bold/italic spacing)
    # For wenqiao .mid.md content, keep emphasis spacing unchanged to avoid
    # large style churn in long-form manuscripts.
    text = fix_common_errors(original, fix_emphasis_spacing=not is_mid)

    # 步骤 2: rumdl 格式化（可跳过）
    # Step 2: rumdl formatting (optional)
    if not skip_rumdl:
        text = _run_rumdl(text)

    # Wenqiao .mid.md files should avoid round-trip rendering because it may
    # rewrite citation/reference and figure structures into non-mid forms.
    if is_mid:
        formatted = text
    else:
        filename = str(input)
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
        if show_stats:
            _emit_stats(original, formatted, target=input, changed=not is_clean)
        if not is_clean:
            raise SystemExit(1)
        return

    # 写入输出 (Write output)
    target = output if output is not None else input
    target.write_text(formatted, encoding="utf-8")
    click.echo(f"Formatted {target}")
    if show_stats:
        _emit_stats(original, formatted, target=target, changed=not is_clean)
