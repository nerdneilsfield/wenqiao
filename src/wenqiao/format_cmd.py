"""format 子命令：规范化学术 Markdown 源文件。

Format subcommand: normalize academic Markdown source files.
Pipeline: fix common errors → rumdl → wenqiao round-trip.
流水线：修复常见错误 → rumdl 格式化 → wenqiao 往返规范化。
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

    # 步骤 1: 修复常见错误（数学双反斜杠、数学/加重/斜体间距）
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
