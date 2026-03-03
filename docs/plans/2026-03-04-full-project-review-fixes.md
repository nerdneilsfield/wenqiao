# Full Project Review Fix Plan (Phase 1–5)

**Date:** 2026-03-04
**Scope:** All issues identified by two independent full-project reviews
**Baseline:** 374 tests pass, ruff 0, mypy 0
**Target:** ~385+ tests, all checks green, security hardened

---

## Context

Two independent static reviews examined the full md-mid codebase (Phases 1–5).
Reviews identified security vulnerabilities, state bugs, correctness issues, and
cleanup opportunities. This plan consolidates and prioritizes all findings.

### Design Decisions Made

1. **HTML RawBlock XSS** → Sanitize with tag/attribute allowlist (no external dep)
2. **LaTeX escaping** → Treat as security + correctness (escape both code inline and URLs)

---

## P0 — Security (Must Fix)

### P0-5: MarkdownRenderer `_native_fn_defs` state leak

**File:** `src/md_mid/markdown.py:113,124`
**Problem:** `render()` resets `_fig_count`, `_tab_count`, `_list_depth` but NOT
`_native_fn_defs`. Second `.render()` call carries stale footnote definitions.

**Fix:** Add `self._native_fn_defs = {}` to the reset block at line 124.

```python
# In render(), after existing resets:
self._native_fn_defs = {}  # Reset native footnote definitions (重置原生脚注定义)
```

**Tests:**
- `test_markdown_renderer_no_state_leak` — render doc A with footnotes, render doc B without → B has no footnotes

---

### P0-1: LaTeX `render_code_inline` unescaped content

**File:** `src/md_mid/latex.py:456-458`
**Problem:** `ci.content` passed raw into `\texttt{}`. Content like `a_b` or `{`
breaks LaTeX compilation. `\input{/etc/passwd}` is command injection.

**Fix:** Import `escape_latex` (not `escape_latex_with_protection` — code inline
should not preserve LaTeX commands) and apply:

```python
from md_mid.escape import escape_latex, escape_latex_with_protection

def render_code_inline(self, node: Node) -> str:
    ci = cast(CodeInline, node)
    return f"\\texttt{{{escape_latex(ci.content)}}}"
```

**Tests:**
- `test_code_inline_escapes_special_chars` — content `a_b{c}` → `\texttt{a\_b\{c\}}`

---

### P0-2: LaTeX `render_link` URL unescaped

**File:** `src/md_mid/latex.py:464-467`
**Problem:** `lnk.url` raw in `\href{}`. URLs with `%`, `#`, `{` break compilation.

**Fix:** Add URL-specific LaTeX escape function (only `\`, `%`, `#`, `{`, `}` need
escaping in `\href` first argument):

```python
def _escape_url_for_latex(url: str) -> str:
    """Escape special chars in URL for \\href (URL LaTeX 特殊字符转义)."""
    return (
        url.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("#", "\\#")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )

def render_link(self, node: Node) -> str:
    lnk = cast(Link, node)
    text = self.render_children(node)
    return f"\\href{{{_escape_url_for_latex(lnk.url)}}}{{{text}}}"
```

**Tests:**
- `test_link_url_escapes_percent` — URL `https://x.com/a%20b#sec` → proper escaping

---

### P0-3: HTML link scheme bypass with control characters

**File:** `src/md_mid/html.py:409`
**Problem:** `.strip()` only removes whitespace. `\t`, `\n`, `\x00` within the scheme
string can bypass the blacklist (e.g. `java\tscript:`).

**Fix:** Strip all ASCII control characters before scheme checking:

```python
# Near top of file, after _SAFE_WIDTH_RE (在 _SAFE_WIDTH_RE 之后)
_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# In _render_link:
cleaned = _CTRL_CHARS_RE.sub("", url).strip().lower()
if cleaned.startswith(_UNSAFE_SCHEMES):
    return text
```

**Tests:**
- `test_link_tab_in_scheme_blocked` — `"java\tscript:alert(1)"` → text only, no href

---

### P0-4: HTML RawBlock sanitization with allowlist

**Files:** NEW `src/md_mid/sanitize.py`, `src/md_mid/html.py:359`
**Problem:** Raw HTML blocks from parser (`html: True`) pass through unescaped.
XSS risk if input is untrusted.

**Fix:** Create `sanitize.py` with a lightweight tag/attribute allowlist sanitizer
using stdlib `html.parser`. No external dependency.

**Allowlist (safe tags):**
```
div, span, p, br, hr, a, img, table, thead, tbody, tr, th, td,
ul, ol, li, dl, dt, dd, h1-h6, blockquote, pre, code, em, strong,
sub, sup, figure, figcaption, details, summary, abbr, mark, del, ins
```

**Safe attributes:** `class`, `id`, `href` (validated), `src` (validated), `alt`,
`title`, `style` (CSS property allowlist), `colspan`, `rowspan`, `align`

**Stripped:** All `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `<form>`,
`<input>`, event handlers (`on*`), `javascript:` in href/src.

**Integration:**
```python
# html.py _render_raw_block:
def _render_raw_block(self, node: Node) -> str:
    rb = cast(RawBlock, node)
    if rb.kind == "html":
        from md_mid.sanitize import sanitize_html
        return sanitize_html(rb.content) + "\n"
    ...
```

**Tests:**
- `test_raw_html_script_stripped` — `<script>alert(1)</script><p>ok</p>` → `<p>ok</p>`
- `test_raw_html_safe_div_preserved` — `<div class="note">text</div>` → unchanged
- `test_raw_html_event_handler_stripped` — `<p onclick="x">` → `<p>`

---

## P1 — Functional Correctness

### P1-3: `--generate-figures` runs before target validation

**File:** `src/md_mid/cli.py:179-216`
**Problem:** AI figure generation (network calls, file writes) runs even if
`effective_target` is invalid (e.g. typo from config file), wasting resources.

**Fix:** Move target validation before the `generate_figures` block:

```python
# After effective_target is set (~line 163), BEFORE generate_figures:
if effective_target not in ("latex", "markdown", "html"):
    click.echo(f"Target '{effective_target}' not yet implemented.", err=True)
    raise SystemExit(1)

# Then: Optional AI figure generation...
if generate_figures:
    ...
```

Remove the duplicate `else` branch at the end of the target `if/elif` chain.

**Tests:**
- `test_generate_figures_invalid_target_no_side_effect` — config `target: invalid` + `--generate-figures` exits before runner loads

---

### P1-1: HTML footnote list order doesn't match ref numbering

**File:** `src/md_mid/html.py:473-478`
**Problem:** `_fn_ref_order` assigns sequential numbers by encounter order of refs.
`_fn_defs` iterates in definition-insertion order. If a footnote is defined in source
before it's referenced, the `<ol>` list position won't match the `[N]` superscript.

**Fix:** Sort footnote list by `_fn_ref_order`:

```python
# In _render_footnotes():
if self._fn_defs:
    parts.append('<div class="footnotes">\n<hr>\n<ol>\n')
    ordered = sorted(
        self._fn_defs.items(),
        key=lambda kv: self._fn_ref_order.get(kv[0], 999),
    )
    for def_id, content in ordered:
        parts.append(f'  <li id="fn-{_esc(def_id)}">{content}</li>\n')
    parts.append("</ol>\n</div>\n")
```

**Tests:**
- `test_footnote_list_matches_ref_order` — define [^b] then [^a], reference [^a] then [^b] → list order is a, b

---

### P1-2: Config type validation for critical fields

**File:** `src/md_mid/config.py:94-121`
**Problem:** `from_dict` passes through any type without checking. `classoptions: 12`
(int) → crash at `latex.py:126` during `cast(list[str], ...)`.

**Fix:** Add type assertions for fields that are cast downstream:

```python
# Type constraints for fields that renderers cast (渲染器依赖的字段类型约束)
_LIST_FIELDS = {"classoptions", "packages", "preamble"}
_DICT_FIELDS = {"package_options"}

# In from_dict, after normalization loop, before return:
for key in _LIST_FIELDS:
    if key in kwargs and not isinstance(kwargs[key], list):
        raise TypeError(
            f"Config '{key}' must be a list, got {type(kwargs[key]).__name__}"
            f" (配置 '{key}' 必须为列表)"
        )
for key in _DICT_FIELDS:
    if key in kwargs and not isinstance(kwargs[key], dict):
        raise TypeError(
            f"Config '{key}' must be a dict, got {type(kwargs[key]).__name__}"
            f" (配置 '{key}' 必须为字典)"
        )
```

**Tests:**
- `test_config_type_error_classoptions_int` — `{"classoptions": 12}` → `TypeError`
- `test_config_type_error_packages_str` — `{"packages": "numpy"}` → `TypeError`

---

### P1-4: Trust boundary documentation for genfig runner

**Files:** `src/md_mid/genfig.py:105-124`, `src/md_mid/cli.py` (help text)
**Problem:** `_load_runner` executes arbitrary Python via `exec_module`. Trust boundary
is undocumented.

**Fix:** Docstring and CLI help text updates only:

```python
# genfig.py _load_runner docstring:
"""...
SECURITY WARNING / 安全警告:
    This function executes arbitrary Python code from the specified file.
    Only use runner scripts from trusted sources.
    此函数执行指定文件中的任意 Python 代码，仅使用受信任的 runner 脚本。
"""

# cli.py --figures-runner help:
help="Path to nanobanana-compatible runner script (WARNING: executes as Python)"
```

No tests needed.

---

## P2 — Cleanup & Performance

### P2-1: Remove dead code `_extract_text_from_tree`

**File:** `src/md_mid/parser.py:326-333`
**Problem:** Only self-recursive calls, no external callers. Replaced by
`_build_children` in Phase 3.

**Fix:** Delete the function (6 lines).

---

### P2-2: `skip_indices` list → set

**File:** `src/md_mid/comment.py:442,486,495`
**Problem:** `j in skip_indices` is O(n) per check on a list.

**Fix:** Change `to_remove: list[int]` → `set[int]`, `skip_indices: list[int]` → `set[int]`:

```python
# _process_attachments_in:
to_remove: set[int] = set()
...
to_remove.add(i)
...
for i in sorted(to_remove, reverse=True):
    children.pop(i)

# _find_prev_sibling signature:
def _find_prev_sibling(
    children: list[Node], current_idx: int, skip_indices: set[int]
) -> Node | None:
```

---

### P2-3: `genfig._walk()` → generator

**File:** `src/md_mid/genfig.py:37-49`
**Problem:** Materializes full node list before processing.

**Fix:** Convert to generator:

```python
from collections.abc import Iterator

def _walk(node: Node) -> Iterator[Node]:
    """Recursively yield all descendant nodes (递归生成所有后代节点)."""
    yield node
    for child in node.children:
        yield from _walk(child)
```

---

## Files Modified Summary

| File | Fixes | Type |
|------|-------|------|
| `src/md_mid/markdown.py` | P0-5 | 1-line state reset |
| `src/md_mid/latex.py` | P0-1, P0-2 | Escape functions + import |
| `src/md_mid/html.py` | P0-3, P1-1 | Control char regex + footnote ordering |
| `src/md_mid/sanitize.py` | P0-4 | NEW — allowlist HTML sanitizer |
| `src/md_mid/cli.py` | P1-3, P1-4 | Target validation reorder + help text |
| `src/md_mid/config.py` | P1-2 | Type validation |
| `src/md_mid/genfig.py` | P1-4, P2-3 | Docstring + generator |
| `src/md_mid/parser.py` | P2-1 | Dead code removal |
| `src/md_mid/comment.py` | P2-2 | list → set |
| `tests/test_markdown.py` | P0-5 | 1 new test |
| `tests/test_latex.py` | P0-1, P0-2 | 2 new tests |
| `tests/test_html.py` | P0-3, P0-4, P1-1 | 5 new tests |
| `tests/test_config.py` | P1-2 | 2 new tests |
| `tests/test_cli.py` | P1-3 | 1 new test |

**Total: 12 fixes, 11 new tests, 1 new file**

---

## Execution Order

```
P0-5 (1-line fix) → P0-1 → P0-2 → P0-3 → P0-4 (new module) →
P1-3 → P1-1 → P1-2 → P1-4 (docs only) →
P2-1 → P2-2 → P2-3
```

All P0s are independent. P1s are independent. P2s are independent.
Within each tier, order follows risk/complexity (simplest first).

---

## Verification

```bash
make check   # ruff 0, mypy 0, all tests green (≥ 374 + 11 new = ~385+)
```

Spot-checks:
- `\texttt{a_b}` → `\texttt{a\_b}` in LaTeX output
- `java\tscript:x` link → text only in HTML
- `<script>` in raw HTML block → stripped
- Render two docs sequentially → no footnote bleed
- `classoptions: 12` in YAML → clear TypeError
- `--generate-figures -t invalid` → exits before runner loads
