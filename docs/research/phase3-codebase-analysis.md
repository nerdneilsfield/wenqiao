# Phase 3 Codebase Analysis (Phase 3 代码分析)

Research notes for Phase 3 implementation. All file paths relative to project root.

---

## 1. Current Table Node Fields (当前 Table 节点字段)

**File:** `src/md_mid/nodes.py`, lines 127-134

```python
@dataclass
class Table(Node):
    headers: list[str] = field(default_factory=list)
    alignments: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
```

- `Table` inherits from `Node`, which provides `children`, `metadata`, `position`.
- `Table` does NOT override `to_dict()` -- it uses the base `Node.to_dict()` which auto-serializes extra fields via `dataclasses.fields()`. The base `to_dict()` (lines 24-44) iterates all fields, special-cases `children`/`metadata`/`position`, and dumps everything else as `result[f.name] = val`. For strings and `list[str]`, this works fine. For `list[list[Node]]`, the coder MUST override `to_dict()` to call `n.to_dict()` on each node.
- No `CellContent` / `TableRow` type aliases exist yet.

---

## 2. How `_build_children()` Works (构建子节点流程)

**File:** `src/md_mid/parser.py`, lines 112-122

```python
def _build_children(node: SyntaxTreeNode) -> list[Node]:
    result: list[Node] = []
    for child in node.children:
        built = _build_node(child)
        if built is not None:
            if isinstance(built, list):
                result.extend(built)
            else:
                result.append(built)
    return result
```

- Recursively walks SyntaxTreeNode children.
- `_build_node()` (lines 125-141) checks for `inline` type (returns `_build_children(node)` -- flattens inline wrapper), then looks up `_NODE_MAP`, falls back to recursive children.
- Calling `_build_children(cell)` on a table cell SyntaxTreeNode will produce nodes like `Text`, `Strong`, `Emphasis`, `CodeInline`, `MathInline`, `Link`, etc. -- exactly the rich inline nodes we need.
- Returns `list[Node]`, which maps directly to `CellContent` in the plan.

---

## 3. How `_build_table()` Currently Works (当前表格构建逻辑)

**File:** `src/md_mid/parser.py`, lines 201-231

- Iterates `node.children` looking for `thead` and `tbody` sections.
- For `thead`: iterates `tr` > `cell`, calls `_extract_text_from_tree(cell)` -> plain `str`, appends to `headers: list[str]`.
- For `tbody`: same pattern, calls `_extract_text_from_tree(cell)` -> plain `str`, appends to `row: list[str]`.
- Alignment extraction from `cell.attrGet("style")` is inline with the header loop. This stays the same.
- `_extract_text_from_tree()` (lines 325-332) recursively extracts plain text from SyntaxTreeNode, discarding all formatting. THIS IS THE DATA LOSS BUG.

**Change needed:** Replace `_extract_text_from_tree(cell)` with `_build_children(cell)` for both headers and rows. Update type annotations from `list[str]` to `list[list[Node]]` etc.

---

## 4. `render_table()` in LaTeX Renderer (LaTeX 表格渲染)

**File:** `src/md_mid/latex.py`, lines 287-324

```python
def render_table(self, node: Node) -> str:
    tbl = cast(Table, node)
    # ... caption, label, placement from metadata
    # Column alignment
    col_spec = "".join(align_map.get(a, "l") for a in tbl.alignments)
    if not col_spec:
        col_spec = "l" * len(tbl.headers)
    # Header row
    header_row = " & ".join(escape_latex(h) for h in tbl.headers)   # <-- CHANGE
    # Data rows
    for row in tbl.rows:
        data_row = " & ".join(escape_latex(cell) for cell in row)   # <-- CHANGE
```

**Change needed:**
- Add `_render_nodes(self, nodes: list[Node]) -> str` helper that joins `self.render(n)` for each node.
- Replace `escape_latex(h)` with `self._render_nodes(h)` for headers.
- Replace `escape_latex(cell)` with `self._render_nodes(cell)` for rows.
- The existing `render_strong()`, `render_emphasis()`, `render_code_inline()`, `render_math_inline()` etc. already produce correct LaTeX. So `self.render()` on cell nodes will produce `\textbf{...}`, `\textit{...}`, `\texttt{...}`, `$...$` automatically.

**Important:** `LaTeXRenderer` has a public `render()` method (line 65) that dispatches to `render_{type}`. It also has `render_children()` (line 78). The new `_render_nodes()` should use `self.render(n)` not `self.render_children()`.

---

## 5. `_render_table()` in Markdown Renderer (Markdown 表格渲染)

**File:** `src/md_mid/markdown.py`, lines 327-371

```python
def _render_table(self, node: Node) -> str:
    t = cast(Table, node)
    # ... tab_count, label, caption from metadata
    # Table headers:
    th_cells = "".join(f"<th>{_esc(h)}</th>" for h in t.headers)      # <-- CHANGE
    # Data rows:
    td_cells = "".join(f"<td>{_esc(cell)}</td>" for cell in row)      # <-- CHANGE
```

**Change needed:**
- Add `_render_cell_html(self, nodes: list[Node]) -> str` and `_render_node_html(self, node: Node) -> str` methods.
- Replace `_esc(h)` with `self._render_cell_html(h)` for headers.
- Replace `_esc(cell)` with `self._render_cell_html(cell)` for rows.
- `_render_node_html()` must handle: `Text` -> `_esc()`, `Strong` -> `<strong>`, `Emphasis` -> `<em>`, `CodeInline` -> `<code>`, `MathInline` -> `$...$`, `Link` -> `<a href>`, `Citation`, `CrossRef`, `SoftBreak` -> space, `HardBreak` -> `<br>`.

**Security note:** ALL text output in `_render_node_html()` MUST go through `_esc()`. The existing `_esc()` function (line 37-39) uses `html.escape(text, quote=True)`.

**Imports needed:** The markdown.py file currently does NOT import `Strong`, `Emphasis`, `SoftBreak`, `HardBreak` from `md_mid.nodes`. These must be added to the import list (line 15-34).

---

## 6. `_render_list()` and `_render_list_item()` -- Nesting Gap (列表嵌套缺陷)

**File:** `src/md_mid/markdown.py`, lines 224-236

```python
def _render_list(self, node: Node) -> str:
    lst = cast(List, node)
    parts: list[str] = []
    for i, item in enumerate(lst.children, start=lst.start):
        marker = f"{i}." if lst.ordered else "-"
        content = self._dispatch(item).strip()
        parts.append(f"{marker} {content}")
    return "\n".join(parts) + "\n\n"

def _render_list_item(self, node: Node) -> str:
    return self._render_children(node).strip()
```

**Current behavior:** No depth tracking. All list items are rendered at the same indentation level regardless of nesting. A nested `List` inside a `ListItem` would be rendered by `_dispatch()` which calls `_render_list()` again, but with zero indentation.

**Change needed:**
- Add `self._list_depth: int = 0` to `__init__()`.
- In `_render_list()`, compute `indent = "  " * self._list_depth`, increment `self._list_depth` before processing items, decrement after.
- Add `_render_list_item_content()` to handle multi-child list items (paragraph + nested list) with proper continuation indentation.

**Note:** The `__init__` signature currently has NO `_list_depth`. It also has no `_locale` or `_mode`. These all need adding.

---

## 7. `MarkdownRenderer.__init__()` Current Full Signature (当前完整签名)

**File:** `src/md_mid/markdown.py`, lines 53-74

```python
def __init__(
    self,
    bib: dict[str, str] | None = None,
    heading_id_style: str = "attr",
    diag: DiagCollector | None = None,
) -> None:
```

Instance variables set:
- `self._bib = bib or {}`
- `self._heading_id_style = heading_id_style`
- `self._diag = diag or DiagCollector("unknown")`
- `self._index: MarkdownIndex = MarkdownIndex()`
- `self._fig_count: int = 0`
- `self._tab_count: int = 0`

**New parameters needed by Phase 3:**
- `locale: str = "zh"` (Task 5) -- for figure/table label i18n
- `mode: str = "full"` (Task 7) -- for body/fragment support

**New instance variables needed:**
- `self._list_depth: int = 0` (Task 4) -- for nested list indentation
- `self._locale = locale` (Task 5)
- `self._labels = _LABEL_STRINGS.get(locale, _LABEL_STRINGS["zh"])` (Task 5)
- `self._mode = mode` (Task 7)

---

## 8. CLI `main()` Function Analysis (CLI 主函数分析)

**File:** `src/md_mid/cli.py`, lines 18-108

Current click decorators and parameters:
```python
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.option("-t", "--target", type=click.Choice(["latex", "markdown", "html"]), default="latex")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
@click.option("--mode", type=click.Choice(["full", "body", "fragment"]), default="full")
@click.option("--strict", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.option("--dump-east", is_flag=True, default=False)
@click.option("--bib", "bib_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--heading-id-style", type=click.Choice(["attr", "html"]), default="attr")
@click.version_option(version=__version__)
```

**Current MarkdownRenderer instantiation** (lines 91-95):
```python
renderer_md = MarkdownRenderer(
    bib=bib,
    heading_id_style=heading_id_style,
    diag=diag,
)
```

**Changes needed for Phase 3:**
- Task 5: Add `--locale` option (`click.Choice(["zh", "en"])`, default `"zh"`). Pass `locale=locale` to `MarkdownRenderer`.
- Task 6: Change `input` argument from `click.Path(exists=True, ...)` to `click.Path(path_type=Path)` (remove `exists=True`). Handle `-` for stdin (`sys.stdin.read()`). Handle `-o -` for stdout (`click.echo()`). Suppress "Written to" message when stdout.
- Task 7: Pass `mode=mode` to `MarkdownRenderer`. The `--mode` option already exists (line 26) but is only passed to `LaTeXRenderer` (line 75). Need to pass it to `MarkdownRenderer` as well.

**Important note about mode:** The `mode` CLI option already exists and is passed to `LaTeXRenderer(mode=mode)` at line 75. For Task 7, we just need to also pass it when constructing `MarkdownRenderer`.

---

## 9. Existing Test Patterns (现有测试模式)

### `tests/test_nodes.py`
- Simple standalone functions: `test_table()`, `test_text_node()`, etc.
- Direct node construction: `Table(headers=["A", "B"], alignments=["left", "right"], rows=[["1", "2"]])`
- Existing `test_table()` at line 74 uses string headers/rows. Must be updated.

### `tests/test_latex.py`
- `render(node, **kwargs)` helper (line 29): creates `LaTeXRenderer(**kwargs).render(node)`.
- NO `doc()` helper -- tests pass nodes directly to `render()`.
- `TestTable.test_basic_table()` (line 325) uses string headers/rows. Must be updated with `_cells()` / `_rows()`.
- Existing `TestFigure`, `TestCiteRef`, `TestFullDocument`, `TestBodyMode`, `TestFragmentMode`, `TestDiagnostics` classes.

### `tests/test_markdown.py`
- `render(node, **kwargs)` helper (line 29): creates `MarkdownRenderer(**kwargs).render(node)`.
- `doc(*children)` helper (line 33): creates `Document(children=list(children))`.
- Tests organized in classes: `TestInline`, `TestBlock`, `TestCrossRef`, `TestHeadingLabel`, `TestCitation`, `TestFigure`, `TestTable`, `TestRawBlock`, `TestFrontMatter`, `TestHtmlEscaping`, `TestUnhandledNodeWarning`.
- `TestTable` class (lines 325-364) has 3 tests, all using string headers/rows. Must be updated with `_cells()` / `_rows()`.
- `TestHtmlEscaping.test_table_cell_ampersand_escaped()` (line 454) uses string rows. Must be updated.

### `tests/test_cli.py`
- Uses `click.testing.CliRunner` and `main` from `md_mid.cli`.
- Pattern: `CliRunner().invoke(main, [str(src), ...opts...])`
- `tmp_path` fixture for temporary files.
- Tests check `result.exit_code == 0` and file content assertions.

---

## 10. Import Patterns and Gotchas (导入模式和注意事项)

### `src/md_mid/nodes.py`
- Uses `from __future__ import annotations`
- Imports: `dataclasses`, `dataclass`, `field`
- All nodes are `@dataclass` subclasses of `Node`
- Forward reference to `"Node"` is needed in type aliases (e.g., `CellContent = list["Node"]`)

### `src/md_mid/parser.py`
- Imports all node types from `md_mid.nodes` (lines 17-43)
- `_build_children()` and `_build_node()` are module-level functions, not methods
- `_NODE_MAP` uses lambda wrappers for some builders (e.g., `lambda n: _build_list(n, ordered=False)`)

### `src/md_mid/latex.py`
- Imports: `escape_latex`, `escape_latex_with_protection` from `md_mid.escape`
- LaTeXRenderer.render() dispatches via `f"render_{node.type}"` (public methods, no underscore prefix)
- Does NOT import `Strong`, `Emphasis`, `SoftBreak`, `HardBreak`, `Paragraph`, `ListItem`, `Blockquote` -- these are handled by generic `render_children()` path. But they ARE imported indirectly via `render_strong()` etc.

### `src/md_mid/markdown.py`
- Uses `from __future__ import annotations`, `import html as _html`, `from typing import cast`
- `_esc()` is a module-level function (not a method): `def _esc(text: str) -> str`
- Dispatch uses `_render_{node.type}` (private methods with underscore prefix -- different from LaTeX!)
- **Currently missing imports that Task 3 needs:** `Strong`, `Emphasis`, `SoftBreak`, `HardBreak` are NOT in the import list. The existing `_render_strong()`, `_render_emphasis()` etc. work because they go through `_dispatch()` which calls `_render_children()`, never checking `isinstance()`. But `_render_node_html()` WILL need `isinstance()` checks, so these imports MUST be added.

### Key Gotcha: Dispatch method naming convention differs
- **LaTeX:** `render_text()`, `render_strong()` -- PUBLIC, no underscore
- **Markdown:** `_render_text()`, `_render_strong()` -- PRIVATE, with underscore
- Both use the same node `type` property for dispatch

### Key Gotcha: `_render_list()` currently uses `_dispatch(item)` for list items
- This calls `_render_list_item()` which returns `self._render_children(node).strip()`.
- When a list item has a nested `List` child, `_render_children()` will call `_dispatch()` on the nested `List`, which calls `_render_list()` recursively. This already happens -- but without indentation tracking.

---

## 11. Hardcoded Locale Strings (硬编码的本地化字符串)

Current hardcoded strings that need localization (Task 5):

**`src/md_mid/markdown.py` -- `_render_figure_block()`** (line 290):
```python
f"  <figcaption><strong>图 {n}</strong>"
```

**`src/md_mid/markdown.py` -- `_render_table()`** (line 362):
```python
f"  <figcaption><strong>表 {n}</strong>"
```

Both appear twice (with and without caption). Four substitution points total.

---

## 12. `render()` Method in MarkdownRenderer (渲染方法分析)

**File:** `src/md_mid/markdown.py`, lines 76-106

```python
def render(self, doc: Document) -> str:
    self._fig_count = 0
    self._tab_count = 0
    self._index = self._build_index(doc)

    parts: list[str] = []
    front_matter = self._render_front_matter(doc)
    if front_matter:
        parts.append(front_matter)
    body = self._render_children(doc)
    parts.append(body)
    footnotes = self._render_footnotes()
    if footnotes:
        parts.append(footnotes)
    return "\n".join(p for p in parts if p)
```

**For Task 7 (mode support):**
- Wrap front matter in `if self._mode == "full":` guard.
- Wrap footnotes in `if self._mode in ("full", "body"):` guard.
- Body is always rendered.
- Reset `self._list_depth = 0` here too (Task 4).

---

## 13. Test Count Summary (测试数量)

Current: **209 tests**, all passing (0.42s).

Breakdown by file:
- `test_cli.py`: ~12 tests
- `test_e2e.py`: ~100+ tests (fixture-driven)
- `test_latex.py`: ~30 tests
- `test_markdown.py`: ~40 tests
- `test_nodes.py`: ~9 tests
- `test_parser.py`: ~15 tests
- Others: comment, bibtex, escape, diagnostic tests

Phase 3 plan estimates ~209+ after changes, though adding new test classes (TestTableRichCells, TestNestedList, TestLocale, TestMarkdownModes, etc.) will likely bring total to ~240+.
