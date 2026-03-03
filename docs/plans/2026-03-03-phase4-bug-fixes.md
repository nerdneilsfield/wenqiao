# Phase 4 Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix four confirmed bugs discovered by external auditors: missing config-to-renderer metadata injection, ineffective `default-target` config key, uncaught `include-tex` file-read exceptions, and footnote circular-expansion `RecursionError`.

**Architecture:** All four fixes are independent and touch at most two files each. Each fix follows the same pattern: write failing test → implement minimal fix → verify green → commit.

**Tech Stack:** Python 3.11+, pytest, click, ruamel.yaml. Run tests with `make test`; run full checks with `make check`.

---

## Background: What Was Audited

Three external auditors reviewed Phase 4. After filtering false positives (e.g., claims that Task 8/9 were never implemented — they were), four confirmed bugs remain. All other reported issues are either design decisions or out-of-scope for this codebase.

**False positives rejected:**
- "Task 8 list args not implemented" — already done at `latex.py:282-286`
- "Task 9 two-pass footnote not implemented" — already done at `latex.py:91-103, 446-473`
- "Symlink path-traversal bypass" — both `resolve()` calls in the traversal check happen in the same iteration; consistent
- "File size limit for include-tex" — out of scope for academic writing tool
- "locale='zh' should auto-inject ctex" — design decision (user configures packages)

---

## Task 1: Inject `title/author/date/abstract` from Config into LaTeX

**Problem:** `cli.py:143-152` calls `east.metadata.update({...})` before rendering. This dict is missing `title`, `author`, `date`, `abstract`. If a user sets these in a config file or template (rather than via `<!-- title: ... -->` document directives), they are silently ignored and `\title{}` / `\author{}` / `\date{}` / `\begin{abstract}` never appear in the output.

**Root cause:** `cfg.title`, `cfg.author`, `cfg.date`, `cfg.abstract` are correctly resolved through the priority chain by `resolve_config()` but never fed back into `east.metadata` for `render_document()` to consume.

**Why the fix is safe:** `render_document()` reads `title/author/date/abstract` from `node.metadata` (same dict as `east.metadata`) and only emits them when non-empty (`if val := meta.get(key)`). Injecting `cfg.title = ""` (the default) is harmless — the renderer skips empty values.

**Files:**
- Modify: `src/md_mid/cli.py:143-152`
- Test: `tests/test_cli.py`

---

**Step 1: Write the failing test**

In `tests/test_cli.py`, add after `test_cli_latex_locale_english`:

```python
def test_cli_config_title_author_injected(tmp_path: Path) -> None:
    """Config-file title/author/date/abstract appear in LaTeX output (配置文件元数据注入到 LaTeX 输出)."""
    cfg = tmp_path / "md-mid.yaml"
    cfg.write_text(
        "title: Config Title\n"
        "author: Config Author\n"
        "date: 2026-01-01\n"
        "abstract: Config abstract text.\n"
    )
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--config", str(cfg)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\title{Config Title}" in content
    assert "\\author{Config Author}" in content
    assert "\\date{2026-01-01}" in content
    assert "Config abstract text." in content
```

**Step 2: Run to verify FAIL**

```bash
uv run pytest tests/test_cli.py::test_cli_config_title_author_injected -v
```
Expected: `FAILED` — `\\title{Config Title}` not in output.

**Step 3: Implement the fix**

In `src/md_mid/cli.py`, find the `east.metadata.update({...})` block (~line 143). Add the four missing fields:

```python
        east.metadata.update({
            "documentclass": cfg.documentclass,
            "classoptions": cfg.classoptions,
            "packages": cfg.packages,
            "package_options": cfg.package_options,
            "bibliography": cfg.bibliography,
            "bibstyle": cfg.bibstyle,
            "preamble": cfg.preamble,
            "bibliography_mode": cfg.bibliography_mode,
            # Metadata fields — empty string is falsy, renderer skips them
            # (元数据字段 — 空字符串为假值，渲染器跳过)
            "title": cfg.title,
            "author": cfg.author,
            "date": cfg.date,
            "abstract": cfg.abstract,
        })
```

**Step 4: Run to verify PASS**

```bash
uv run pytest tests/test_cli.py::test_cli_config_title_author_injected -v
```
Expected: `PASSED`.

**Step 5: Run full suite**

```bash
make test
```
Expected: all tests pass (≥ 299).

**Step 6: Commit**

```bash
git add src/md_mid/cli.py tests/test_cli.py
git commit -m "fix(cli): inject title/author/date/abstract from config into LaTeX metadata"
```

---

## Task 2: Honour `default-target` from Config File

**Problem:** `cli.py` branches on `target` (the Click parameter), which always has `default="latex"`. `cfg.target` — correctly resolved from the priority chain (document directive > config file > template > default) — is computed but never used. A user setting `default-target: markdown` in their config file gets no effect.

**Root cause:** The `--target` Click option has `default="latex"`, so when the user omits `--target`, `target == "latex"` even if the config says otherwise. There is no way to distinguish "user explicitly said latex" from "user said nothing, CLI defaulted".

**Fix:** Change `--target` to `default=None`. After `cfg = resolve_config(...)`, compute:
```python
effective_target = target if target is not None else cfg.target
```
Use `effective_target` everywhere `target` was used for branching.

**Files:**
- Modify: `src/md_mid/cli.py:23-26` (option default) and `cli.py:140-190` (branching)
- Test: `tests/test_cli.py`

---

**Step 1: Write the failing test**

```python
def test_cli_default_target_from_config(tmp_path: Path) -> None:
    """default-target in config file selects the renderer (配置文件 default-target 选择渲染器)."""
    cfg = tmp_path / "md-mid.yaml"
    cfg.write_text("default-target: markdown\n")
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "out.rendered.md"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--config", str(cfg)]
    )
    assert result.exit_code == 0
    # Output is markdown not latex (output 是 Markdown 而非 LaTeX)
    content = out.read_text()
    assert "\\documentclass" not in content
    assert "# Hello" in content
```

**Step 2: Run to verify FAIL**

```bash
uv run pytest tests/test_cli.py::test_cli_default_target_from_config -v
```
Expected: `FAILED` — output contains `\documentclass` (LaTeX rendered instead of Markdown).

**Step 3: Implement the fix**

In `src/md_mid/cli.py`:

3a. Change the `--target` option default:
```python
@click.option(
    "-t", "--target",
    type=click.Choice(["latex", "markdown", "html"]),
    default=None,   # None = not specified; falls back to cfg.target
)
```

3b. After `cfg = resolve_config(...)` (around line 124), add one line:
```python
    cfg = resolve_config(...)

    # Effective target: CLI > config > default "latex" (有效目标：CLI > 配置 > 默认)
    effective_target: str = target if target is not None else cfg.target
```

3c. Replace every use of `target` (for branching) with `effective_target`. There are three places:
- `if target == "latex":` → `if effective_target == "latex":`
- `elif target == "markdown":` → `elif effective_target == "markdown":`
- `f"Target '{target}' not yet implemented."` → `f"Target '{effective_target}' not yet implemented."`

Do NOT change the function parameter name `target` — it is the Click parameter name.

**Step 4: Run to verify PASS**

```bash
uv run pytest tests/test_cli.py::test_cli_default_target_from_config -v
```
Expected: `PASSED`.

**Step 5: Run full suite**

```bash
make test
```
Expected: all tests pass (≥ 300). Check that existing `test_convert_minimal` (which omits `--target`) still passes — it should still produce LaTeX because `cfg.target` defaults to `"latex"`.

**Step 6: Commit**

```bash
git add src/md_mid/cli.py tests/test_cli.py
git commit -m "fix(cli): honour default-target from config file when --target not specified"
```

---

## Task 3: Handle `include-tex` Read Errors Gracefully

**Problem:** `comment.py:413` calls `tex_path.read_text(encoding="utf-8")` without any exception handling. Three failure modes crash the process:

1. **Directory path**: `<!-- include-tex: subdir/ -->` → `IsADirectoryError`
2. **Binary/non-UTF-8 file**: e.g. a compiled `.pdf` included by mistake → `UnicodeDecodeError`
3. **Permission denied**: file exists but not readable → `PermissionError`

All three should be reported as `diag.error()` and the directive skipped (same pattern as "file not found").

**Files:**
- Modify: `src/md_mid/comment.py:405-416`
- Test: `tests/test_comment.py`

---

**Step 1: Write the failing tests**

In `tests/test_comment.py`, add after the existing `include-tex` tests:

```python
def test_include_tex_directory_path(tmp_path: Path) -> None:
    """include-tex 指向目录时报错而不崩溃 (include-tex on a directory path reports error, no crash)."""
    (tmp_path / "subdir").mkdir()
    text = "<!-- include-tex: subdir -->\n"
    raw = parse(text)
    dc = DiagCollector(str(tmp_path / "t.mid.md"))
    east = process_comments(raw, str(tmp_path / "t.mid.md"), diag=dc)
    # Must not raise; must report error (不抛异常，报告错误)
    assert any("include-tex" in d.message for d in dc.errors)
    # The node should remain or be removed, but no RawBlock with dir content
    for child in east.children:
        assert not (hasattr(child, "content") and "subdir" in type(child).__name__.lower())


def test_include_tex_non_utf8_file(tmp_path: Path) -> None:
    """include-tex 指向非 UTF-8 文件时报错而不崩溃 (include-tex on binary file reports error, no crash)."""
    binary = tmp_path / "bad.tex"
    binary.write_bytes(b"\xff\xfe invalid utf8 \x00")
    text = "<!-- include-tex: bad.tex -->\n"
    raw = parse(text)
    dc = DiagCollector(str(tmp_path / "t.mid.md"))
    east = process_comments(raw, str(tmp_path / "t.mid.md"), diag=dc)
    # Must not raise; must report error (不抛异常，报告错误)
    assert any("include-tex" in d.message for d in dc.errors)
```

**Step 2: Run to verify FAIL**

```bash
uv run pytest tests/test_comment.py::test_include_tex_directory_path tests/test_comment.py::test_include_tex_non_utf8_file -v
```
Expected: both `ERROR` (exception propagates, not caught).

**Step 3: Implement the fix**

In `src/md_mid/comment.py`, replace the bare `read_text` call:

```python
                # Read verbatim — no strip() (原样读取 — 不去空白)
                content = tex_path.read_text(encoding="utf-8")
```

with:

```python
                # Read verbatim — wrap errors as diag errors (原样读取 — 错误转为诊断)
                try:
                    content = tex_path.read_text(encoding="utf-8")
                except (IsADirectoryError, UnicodeDecodeError, PermissionError, OSError) as exc:
                    diag.error(
                        f"include-tex could not read file: {tex_rel} ({exc})",
                        _pos_from_node(child),
                    )
                    i += 1
                    continue
```

No imports needed — all exception classes are builtins.

**Step 4: Run to verify PASS**

```bash
uv run pytest tests/test_comment.py::test_include_tex_directory_path tests/test_comment.py::test_include_tex_non_utf8_file -v
```
Expected: both `PASSED`.

**Step 5: Run full suite**

```bash
make test
```
Expected: all tests pass (≥ 302).

**Step 6: Commit**

```bash
git add src/md_mid/comment.py tests/test_comment.py
git commit -m "fix(comment): catch read errors in include-tex (directory, binary, permission)"
```

---

## Task 4: Guard Against Footnote Circular Expansion

**Problem:** `latex.py:459` calls `self.render_children(fn_def)` inside `render_footnote_ref`. If `fn_def` contains a `FootnoteRef` to itself (e.g. `[^1]: see [^1]`), this recurses infinitely until Python raises `RecursionError`.

Example markdown that triggers the bug:
```
See note.[^1]

[^1]: This note refers to itself.[^1]
```

**Fix:** Track which footnote IDs are currently being expanded using a `_expanding_fn_refs: set[str]` instance variable. If `fr.ref_id` is already in the set, emit a safe fallback instead of recursing.

**Files:**
- Modify: `src/md_mid/latex.py` — `__init__`, `render_document`, `render_footnote_ref`
- Test: `tests/test_latex.py`

---

**Step 1: Write the failing test**

In `tests/test_latex.py`, add to `TestLatexFootnotes`:

```python
    def test_footnote_self_reference_no_recursion(self) -> None:
        """Self-referencing footnote does not cause RecursionError (自引用脚注不引发 RecursionError).

        A FootnoteDef whose children contain a FootnoteRef to itself must
        produce output without infinite recursion. (自引用脚注不应无限递归。)
        """
        # Build: p[ref→0] fn_def[0: "see " ref→0]
        inner_ref = FootnoteRef(ref_id="0")
        fn_def = FootnoteDef(
            def_id="0",
            children=[Paragraph(children=[Text(content="see "), inner_ref])],
        )
        p = Paragraph(children=[Text(content="Here"), FootnoteRef(ref_id="0")])
        doc = Document(children=[p, fn_def])
        # Must terminate and produce some footnote command (必须终止并产出脚注命令)
        result = LaTeXRenderer().render(doc)
        assert "\\footnote" in result
```

**Step 2: Run to verify FAIL**

```bash
uv run pytest "tests/test_latex.py::TestLatexFootnotes::test_footnote_self_reference_no_recursion" -v
```
Expected: `ERROR` with `RecursionError: maximum recursion depth exceeded`.

**Step 3: Implement the fix**

3a. In `LaTeXRenderer.__init__`, add one attribute after `self._fn_defs`:
```python
        self._expanding_fn_refs: set[str] = set()  # guard against circular expansion (防循环展开守卫)
```

3b. In `render_document`, add a clear after `self._fn_defs.clear()`:
```python
        self._fn_defs.clear()
        self._expanding_fn_refs.clear()  # Reset expansion guard (重置展开守卫)
```

3c. In `render_footnote_ref`, add the guard before expanding:
```python
    def render_footnote_ref(self, node: Node) -> str:
        """Expand footnote inline at reference site (在引用处展开脚注).
        ...
        """
        fr = cast(FootnoteRef, node)
        fn_def = self._fn_defs.get(fr.ref_id)
        if fn_def is not None:
            # Guard: skip if this def is already being expanded (防循环：若已在展开中则跳过)
            if fr.ref_id in self._expanding_fn_refs:
                return f"\\footnote{{[circular:{fr.ref_id}]}}"
            self._expanding_fn_refs.add(fr.ref_id)
            try:
                content = self.render_children(fn_def).strip()
            finally:
                self._expanding_fn_refs.discard(fr.ref_id)
            return f"\\footnote{{{content}}}"
        return f"\\footnote{{[{fr.ref_id}]}}"
```

**Step 4: Run to verify PASS**

```bash
uv run pytest "tests/test_latex.py::TestLatexFootnotes::test_footnote_self_reference_no_recursion" -v
```
Expected: `PASSED`.

**Step 5: Run full suite and type-check**

```bash
make check
```
Expected: ruff clean, mypy clean, all tests pass (≥ 303).

**Step 6: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "fix(latex): guard against circular footnote expansion with visited set"
```

---

## Files Modified

| File | Tasks | Change |
|------|-------|--------|
| `src/md_mid/cli.py` | 1, 2 | Inject title/author/date/abstract; use effective_target |
| `src/md_mid/comment.py` | 3 | Wrap read_text in try/except |
| `src/md_mid/latex.py` | 4 | Add `_expanding_fn_refs` guard |
| `tests/test_cli.py` | 1, 2 | 2 new tests |
| `tests/test_comment.py` | 3 | 2 new tests |
| `tests/test_latex.py` | 4 | 1 new test |

## Verification

```bash
make check   # ruff 0, mypy 0, all tests green (≥ 303 + existing 298 = ~303 total)
```
