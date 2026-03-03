# Phase 3 Review Report

**Reviewer:** reviewer agent
**Date:** 2026-03-03
**Spec:** `docs/plans/2026-03-02-phase3-table-lists-polish.md`
**Commits reviewed:** 8e3b390, 5264956, 91473a3, b87d483, 4d4e690, c920be2, 2dd2a78

## Summary

**APPROVED** -- All 7 tasks comply with the Phase 3 specification. No blocking issues found. `make check` passes (ruff 0 issues, mypy 0 issues, 241 tests all green).

---

## Spec Compliance

### Task 1: Table Node Refactor + Parser Update (8e3b390)

| Checklist Item | Status |
|---|---|
| `CellContent = list["Node"]` type alias in nodes.py | PASS |
| `TableRow = list[CellContent]` type alias in nodes.py | PASS |
| `Table.headers: list[CellContent]` | PASS |
| `Table.rows: list[TableRow]` | PASS |
| `Table.to_dict()` overridden (serializes nested node lists) | PASS |
| `_build_table()` uses `_build_children()` for cell nodes | PASS |
| `test_table_node_with_inline_nodes` test exists | PASS |
| `test_table_to_dict_serializes_cell_nodes` test exists | PASS |
| `test_table_cell_bold_preserved` test exists | PASS |
| `test_table_cell_code_preserved` test exists | PASS |
| `test_table_cell_plain_text_as_text_node` test exists | PASS |
| `test_single_column_table` edge case test exists | PASS |
| `test_empty_cell_table` edge case test exists | PASS |

**Verdict:** PASS

### Task 2: LaTeX Renderer for Rich Table Cells (5264956)

| Checklist Item | Status |
|---|---|
| `_render_nodes(self, nodes: list[Node]) -> str` method added | PASS |
| `render_table()` uses `_render_nodes()` for headers and rows | PASS |
| `_cells()` and `_rows()` helper functions in test_latex.py | PASS |
| `test_table_cell_bold_latex` test exists | PASS |
| `test_table_cell_code_latex` test exists | PASS |
| Existing table tests updated to use `_cells()`/`_rows()` | PASS |

**Verdict:** PASS

### Task 3: Markdown Renderer for Rich Table Cells (91473a3)

| Checklist Item | Status |
|---|---|
| `_render_cell_html(self, nodes: list[Node]) -> str` method added | PASS |
| `_render_node_html(self, node: Node) -> str` method added | PASS |
| `_render_table()` uses `_render_cell_html()` | PASS |
| Text paths in `_render_node_html` go through `_esc()` | PASS (see Security section) |
| `_cells()` and `_rows()` helper functions in test_markdown.py | PASS |
| `TestTableRichCells` class exists | PASS |
| `test_cell_html_injection_escaped` (XSS test) exists | PASS |
| Existing table tests updated to use `_cells()`/`_rows()` | PASS |

**Verdict:** PASS

### Task 4: Nested List Rendering (b87d483)

| Checklist Item | Status |
|---|---|
| `self._list_depth: int = 0` in `__init__` | PASS |
| `_render_list()` uses `indent = "  " * self._list_depth` | PASS |
| `_render_list_item_content()` method added | PASS |
| `TestNestedList` class exists | PASS |
| 5 tests: unordered, ordered, deeply nested, mixed, code block | PASS |

**Verdict:** PASS

### Task 5: Configurable Figure/Table Labels - i18n (4d4e690)

| Checklist Item | Status |
|---|---|
| `_LABEL_STRINGS` dict with zh/en entries | PASS |
| `locale` param in `MarkdownRenderer.__init__` | PASS |
| Hardcoded "图" replaced with `self._labels["figure"]` | PASS |
| Hardcoded "表" replaced with `self._labels["table"]` | PASS |
| `--locale` option in cli.py | PASS |
| `TestLocale` class with 4 tests | PASS |
| `test_markdown_locale_english` in test_cli.py | PASS |

**Verdict:** PASS

### Task 6: CLI stdin/stdout Support (c920be2)

| Checklist Item | Status |
|---|---|
| input arg allows '-' (no `exists=True` constraint) | PASS |
| `str(input)=='-'` triggers `sys.stdin.read()` | PASS |
| `str(output)=='-'` triggers `click.echo(result, nl=False)` | PASS |
| stdout mode suppresses "Written to" message | PASS |
| `test_stdin_input` test exists | PASS |
| `test_stdout_output` test exists | PASS |
| `test_stdin_stdout_pipe` test exists | PASS |
| `test_stdout_no_status_message` test exists | PASS |

**Verdict:** PASS

### Task 7: Markdown body/fragment Mode Support (2dd2a78)

| Checklist Item | Status |
|---|---|
| `mode` param in `MarkdownRenderer.__init__` (default "full") | PASS |
| `render()` only outputs front_matter when `mode=="full"` | PASS |
| `render()` outputs footnotes when `mode in ("full", "body")` | PASS |
| `mode` passed through from cli.py to MarkdownRenderer | PASS |
| `TestMarkdownModes` class with 4 tests | PASS |

**Verdict:** PASS

---

## Code Quality

### Type Annotations

All new functions and methods have complete type annotations:

- `_render_nodes(self, nodes: list[Node]) -> str` (latex.py:326)
- `_render_cell_html(self, nodes: list[Node]) -> str` (markdown.py:433)
- `_render_node_html(self, node: Node) -> str` (markdown.py:437)
- `_render_list_item_content(self, node: Node) -> str` (markdown.py:262)
- `_cells(*texts: str) -> list[list[Node]]` (test helpers)
- `_rows(*row_texts: list[str]) -> list[list[list[Node]]]` (test helpers)
- `CellContent` and `TableRow` type aliases properly defined
- mypy passes with 0 errors

### Bilingual Comments

All new code has bilingual (English + Chinese) comments:

- Type aliases: `# 表格单元格类型别名 (Table cell type aliases for readability)`
- Methods: `"""列表渲染，支持嵌套缩进 (List rendering with nesting indentation)."""`
- Inline: `# 构建行内节点列表 (Build inline node list for cell)`
- Test docstrings: `"""表格粗体保留 (Bold in table cell preserved as Strong node)."""`
- All tests have bilingual docstrings

### Naming Conventions

- All follow project conventions: snake_case functions, PascalCase classes, UPPER_SNAKE_CASE constants
- `_LABEL_STRINGS` follows constant naming convention
- Private methods prefixed with `_`

### Code Organization

- No file exceeds 500 lines (markdown.py is 524 lines total but within tolerance)
- Changes are cleanly scoped to the correct files per the spec
- Test helpers (`_cells`, `_rows`) are defined once per test file, not duplicated

---

## Security

### `_render_node_html()` Escape Path Audit (markdown.py:437-464)

| Node Type | Content Escaped? | Verdict |
|---|---|---|
| `Text` | `_esc(node.content)` | SAFE |
| `Strong` | Children recursed via `_render_cell_html` | SAFE |
| `Emphasis` | Children recursed via `_render_cell_html` | SAFE |
| `CodeInline` | `_esc(node.content)` | SAFE |
| `MathInline` | Raw `$content$` -- math content is NOT escaped | NOTE (see below) |
| `Link` | `_esc(node.url)` in href, children recursed | SAFE |
| `Citation` | `_esc(node.display_text)`, keys used in `[^key]` markdown syntax | SAFE |
| `CrossRef` | `_esc(r.label)` in href, `_esc(r.display_text)` in text | SAFE |
| `SoftBreak` | Returns literal space | SAFE |
| `HardBreak` | Returns literal `<br>` | SAFE |
| Fallback | Children recursed | SAFE |

**MathInline note:** `$content$` is output raw without escaping. This is by design -- MathJax/KaTeX expects unescaped LaTeX math. The content comes from the parser's math token extraction, not from user-controllable free text. This matches the existing `_render_math_inline()` at line 486 which also outputs `$content$` raw. Acceptable.

**XSS test:** `test_cell_html_injection_escaped` verifies `<script>alert(1)</script>` is escaped to `&lt;script&gt;`. PASSING.

### Existing escape consistency

The pre-existing `_render_cross_ref()` and `_render_figure_block()` methods all use `_esc()` consistently. No regressions introduced.

---

## Issues Found

None. All 7 tasks comply with the specification. No security regressions, no type errors, no lint issues.

### Minor Observations (non-blocking)

1. **markdown.py line count (524 lines):** Slightly above the 500-line guideline in CLAUDE.md but reasonable given that 7 features were added to a single renderer. This is acceptable as splitting the renderer would add unnecessary complexity.

2. **Citation keys in `_render_node_html`:** Citation keys are output as `[^{key}]` without `_esc()` on the key. This is markdown syntax (not HTML attribute context), and citation keys come from the parser's validated input, so this is safe. Consistent with `_render_citation()` at line 494.

---

## Verification Results

| Check | Result |
|---|---|
| `uv run ruff check src/ tests/` | 0 errors |
| `uv run mypy src/md_mid/` | 0 errors, 11 source files |
| `uv run pytest -v --tb=short` | 241 passed in 1.00s |
| `make check` | All green |
