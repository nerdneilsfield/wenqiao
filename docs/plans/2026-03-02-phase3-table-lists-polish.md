# Phase 3: Rich Table Cells, Nested Lists & CLI Polish

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix data-loss in table cell parsing (inline formatting stripped), add proper nested list rendering for Markdown, and polish CLI/renderer configurability with stdin/stdout, locale labels, and Markdown modes.

**Architecture:** The table refactor changes `Table.headers` from `list[str]` to `list[list[Node]]` and `Table.rows` from `list[list[str]]` to `list[list[list[Node]]]`. The parser uses `_build_children()` instead of `_extract_text_from_tree()` for cells. The Markdown renderer adds HTML-mode inline rendering for table cells. Nested list rendering adds depth tracking. CLI gains stdin/stdout and Markdown mode support.

**Tech Stack:** Python 3.14, markdown-it-py, ruamel.yaml, click, pytest, standard library `html`

---

## PRD Phase 3 Alignment

PRD §Phase 3 定义了 8 个条目。以下为当前覆盖状态：

| PRD 条目 | 状态 | 说明 |
|---|---|---|
| Figure 环境（caption/label/width/placement/centering） | ✅ Phase 1-2 已实现 | `comment.py` 已处理全部 attach-up 指令，两个 renderer 均渲染 |
| Table 环境（GFM → tabular） | ⚠️ 本计划强化 | Tasks 1-3 修复单元格内行内格式丢失 |
| 代码块（lstlisting/minted，可配置） | ⏳ 延后 | lstlisting 已实现，minted 可配置延至 Phase 4 与模板系统一起做 |
| 列表（含嵌套）、引用块 | ⚠️ 本计划修复 | Task 4 修复 Markdown 嵌套列表；引用块已在两个 renderer 中实现 |
| begin/end 自定义环境（含 options） | ✅ Phase 1 已实现 | `comment.py` `_collect_env_directives()` 收集 options/args |
| 脚注策略定稿 | ✅ 基本已实现 | 重复脚注 ID 的 strict/非strict 策略已在 `parser.py` 中实现 |
| Fragment 模式细化 | ⚠️ 本计划覆盖 | Task 7 泛化 Markdown 的 body/fragment 模式 |
| 复杂表格/片段 raw 透传 | ✅ Phase 1 已实现 | `begin: raw` 在 `comment.py` 中实现 |

**延后到 Phase 4 的内容：**
- lstlisting/minted 可配置（与模板系统一起设计）
- LaTeX renderer 的 locale 支持（由 `\figurename` 等 LaTeX 机制处理）
- PRD §11 Table 节点定义更新（执行完 Task 1 后同步更新 PRD）

---

## Migration Strategy

Task 1 修改 `Table` 的字段类型是 **breaking change**，影响范围如下：

| 影响点 | 变化 | 修复时机 |
|---|---|---|
| `Table.headers` | `list[str]` → `list[list[Node]]` | Task 1 |
| `Table.rows` | `list[list[str]]` → `list[list[list[Node]]]` | Task 1 |
| `Table.to_dict()` JSON 输出 | cells 从字符串变为节点数组 | Task 1 |
| `parser.py` `_build_table()` | `_extract_text_from_tree()` → `_build_children()` | Task 1 |
| `latex.py` `render_table()` | `escape_latex(str)` → `self._render_nodes(list[Node])` | Task 2 |
| `markdown.py` `_render_table()` | `_esc(str)` → `self._render_cell_html(list[Node])` | Task 3 |
| `tests/test_nodes.py` table tests | string args → Node list args | Task 1 |
| `tests/test_parser.py` table tests | assertion on str → assertion on Node types | Task 1 |
| `tests/test_latex.py` table tests | string headers/rows → `_cells()`/`_rows()` helpers | Task 2 |
| `tests/test_markdown.py` table tests | same as above | Task 3 |
| `tests/test_e2e.py` table tests | 无变化（通过 parser 自动适配） | N/A |
| `--dump-east` JSON output | cells 从字符串变为 `{"type":"text","content":...}` | Task 1 |

**注意：** Tasks 1→2→3 必须顺序执行。Task 1 完成后、Task 2 完成前，`test_latex.py` 中的 table 相关测试会失败。

---

## Key Design Decisions

1. **Table cells as Node lists (not strings):** Currently `Table.headers: list[str]` discards inline formatting. Changing to `list[list[Node]]` preserves `Strong`, `Emphasis`, `CodeInline`, `MathInline` etc. in cells. This is the right EAST architecture — everything is nodes.

2. **Markdown table cells render as HTML inline:** Since the Markdown renderer uses HTML `<table>` elements, cell content must be rendered as HTML (not Markdown syntax). `**bold**` inside `<td>` is NOT processed by most Markdown renderers. So we render `<strong>bold</strong>` instead.

3. **LaTeX table cells use existing render methods:** The LaTeX renderer already has `render_strong()` → `\textbf{}`, etc. We just call `render()` on cell nodes instead of `escape_latex()` on strings.

4. **Nested list depth via instance variable:** `self._list_depth` tracks nesting level. Each nested list indents by 2 spaces. This is simpler than passing depth as a parameter (which would break the `_dispatch()` signature).

5. **Test helper for table construction:** Add `_cells()` / `_rows()` helpers in test files to wrap strings as `[Text(content=...)]` nodes. This keeps test updates minimal.

---

## Dependency Graph

```
Task 1 (Table Node + Parser) ──→ Task 2 (LaTeX table) ──→┐
                               └→ Task 3 (MD table)   ──→├── Task 4+ are independent
                                                          │
Task 4 (Nested lists)         ────────────────────────────┤
Task 5 (Locale labels)        ────────────────────────────┤
Task 6 (stdin/stdout)         ────────────────────────────┤
Task 7 (MD mode)              ────────────────────────────┘
```

Tasks 1→2→3 must be sequential (type change cascades). Tasks 4–7 are independent of each other and of 2–3 (but depend on Task 1 being merged).

---

## Task 1: Table Node Refactor + Parser Update

**Files:**
- Modify: `src/md_mid/nodes.py` — Change `Table` fields, override `to_dict()`
- Modify: `src/md_mid/parser.py` — Use `_build_children()` for cells
- Modify: `tests/test_nodes.py` — Update table node tests
- Modify: `tests/test_parser.py` — Add rich table cell tests

**Step 1: Write failing tests**

In `tests/test_nodes.py`, replace existing `test_table` and add:

```python
from md_mid.nodes import Table, Text, Strong

def test_table_node_with_inline_nodes() -> None:
    """表格节点含行内节点 (Table node with inline nodes in cells)."""
    t = Table(
        headers=[[Text(content="A")], [Strong(children=[Text(content="B")])]],
        alignments=["left", "left"],
        rows=[[[Text(content="1")], [Text(content="2")]]],
    )
    assert t.type == "table"
    assert len(t.headers) == 2
    assert len(t.rows) == 1

def test_table_to_dict_serializes_cell_nodes() -> None:
    """表格 to_dict 序列化单元格节点 (Table to_dict serializes cell nodes)."""
    t = Table(
        headers=[[Text(content="H")]],
        alignments=["left"],
        rows=[[[Text(content="V")]]],
    )
    d = t.to_dict()
    assert d["headers"][0][0]["type"] == "text"
    assert d["headers"][0][0]["content"] == "H"
    assert d["rows"][0][0][0]["type"] == "text"
```

In `tests/test_parser.py`, add:

```python
from md_mid.nodes import Table, Strong, CodeInline, Text

def test_table_cell_bold_preserved() -> None:
    """表格粗体保留 (Bold in table cell preserved as Strong node)."""
    doc = parse("| **bold** | plain |\n|---|---|\n| a | b |\n")
    table = [c for c in doc.children if isinstance(c, Table)][0]
    # 第一个表头含 Strong 节点 (First header contains Strong)
    assert any(isinstance(n, Strong) for n in table.headers[0])

def test_table_cell_code_preserved() -> None:
    """表格行内代码保留 (Code in table cell preserved as CodeInline)."""
    doc = parse("| `code` | text |\n|---|---|\n| a | b |\n")
    table = [c for c in doc.children if isinstance(c, Table)][0]
    assert any(isinstance(n, CodeInline) for n in table.headers[0])

def test_table_cell_plain_text_as_text_node() -> None:
    """表格纯文本为 Text 节点 (Plain text cell is Text node)."""
    doc = parse("| hello |\n|---|\n| world |\n")
    table = [c for c in doc.children if isinstance(c, Table)][0]
    assert any(isinstance(n, Text) for n in table.headers[0])
    assert any(isinstance(n, Text) for n in table.rows[0][0])

def test_single_column_table() -> None:
    """单列表格 (Single column table parses correctly)."""
    doc = parse("| H |\n|---|\n| V |\n")
    table = [c for c in doc.children if isinstance(c, Table)][0]
    assert len(table.headers) == 1
    assert len(table.rows) == 1

def test_empty_cell_table() -> None:
    """空单元格表格 (Table with empty cells)."""
    doc = parse("| A | |\n|---|---|\n| | B |\n")
    table = [c for c in doc.children if isinstance(c, Table)][0]
    assert len(table.headers) == 2
    assert len(table.rows[0]) == 2
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_nodes.py::test_table_node_with_inline_nodes tests/test_nodes.py::test_table_to_dict_serializes_cell_nodes tests/test_parser.py::test_table_cell_bold_preserved -v`

Expected: TypeError or assertion failures because Table still uses `list[str]`.

**Step 3: Implement changes**

In `src/md_mid/nodes.py`, add type aliases and modify `Table`:

```python
# 表格单元格类型别名 (Table cell type aliases for readability)
CellContent = list["Node"]   # 单元格内容：行内节点列表 (Cell: list of inline nodes)
TableRow = list[CellContent]  # 表格行：单元格列表 (Row: list of cells)


@dataclass
class Table(Node):
    headers: list[CellContent] = field(default_factory=list)
    alignments: list[str] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)

    @property
    def type(self) -> str:
        return "table"

    def to_dict(self) -> dict[str, object]:
        """Serialize table with inline node cells (序列化含行内节点的表格单元格)."""
        result: dict[str, object] = {"type": self.type}
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        if self.metadata:
            result["metadata"] = self.metadata
        if self.position is not None:
            result["position"] = self.position
        result["headers"] = [
            [n.to_dict() for n in cell] for cell in self.headers
        ]
        result["alignments"] = self.alignments
        result["rows"] = [
            [[n.to_dict() for n in cell] for cell in row]
            for row in self.rows
        ]
        return result
```

Type aliases 使嵌套类型更可读：`list[CellContent]` 即 `list[list[Node]]`，`list[TableRow]` 即 `list[list[list[Node]]]`。

In `src/md_mid/parser.py`, modify `_build_table()`:

Replace all `_extract_text_from_tree(cell)` / `headers.append(text)` / `row.append(...)` with `_build_children(cell)`:

```python
def _build_table(node: SyntaxTreeNode) -> Table:
    headers: list[list[Node]] = []
    alignments: list[str] = []
    rows: list[list[list[Node]]] = []

    for section in node.children:
        if section.type == "thead":
            for tr in section.children:
                for cell in tr.children:
                    # 构建行内节点列表 (Build inline node list for cell)
                    cell_nodes = _build_children(cell)
                    headers.append(cell_nodes)
                    # 对齐信息不变 (Alignment extraction unchanged)
                    style: str = str(cell.attrGet("style") or "")
                    if "left" in style:
                        alignments.append("left")
                    elif "right" in style:
                        alignments.append("right")
                    elif "center" in style:
                        alignments.append("center")
                    else:
                        alignments.append("left")
        elif section.type == "tbody":
            for tr in section.children:
                row: list[list[Node]] = []
                for cell in tr.children:
                    row.append(_build_children(cell))
                rows.append(row)

    return Table(
        headers=headers, alignments=alignments, rows=rows,
        position=_position_from_map(node),
    )
```

Also update the `_build_table` type annotation in `_NODE_MAP` — it already uses `_BuilderFn` which returns `Node | list[Node] | None`, so no change needed there.

**Step 4: Run tests**

Run: `uv run pytest tests/test_nodes.py tests/test_parser.py -v`

Note: `test_latex.py` and `test_markdown.py` table tests will fail at this point — that's expected and fixed in Tasks 2–3.

**Step 5: Commit**

```
refactor(nodes,parser): change Table to Node-based cells for rich inline content
```

---

## Task 2: Update LaTeX Renderer for Rich Table Cells

**Files:**
- Modify: `src/md_mid/latex.py` — Add `_render_nodes()`, update `render_table()`
- Modify: `tests/test_latex.py` — Update table tests to use Node cells

**Step 1: Write failing test**

Add to `tests/test_latex.py`:

```python
from md_mid.nodes import Table, Text, Strong, CodeInline

# 测试辅助函数 (Test helpers for Table cell construction)
def _cells(*texts: str) -> list[list[Node]]:
    """Wrap strings as Text node cells (字符串包装为 Text 节点单元格)."""
    return [[Text(content=t)] for t in texts]

def _rows(*row_texts: list[str]) -> list[list[list[Node]]]:
    """Wrap string rows as Text node rows (字符串行包装为 Text 节点行)."""
    return [[[Text(content=t)] for t in row] for row in row_texts]


def test_table_cell_bold_latex() -> None:
    """表格粗体 LaTeX 渲染 (Bold in table cell renders as \\textbf)."""
    t = Table(
        headers=[[Strong(children=[Text(content="Method")])]],
        alignments=["left"],
        rows=[[[Text(content="RANSAC")]]],
    )
    t.metadata["caption"] = "T"
    result = render(doc(t))
    assert "\\textbf{Method}" in result

def test_table_cell_code_latex() -> None:
    """表格代码 LaTeX 渲染 (Code in table cell renders as \\texttt)."""
    t = Table(
        headers=_cells("H"),
        alignments=["left"],
        rows=[[[CodeInline(content="x=1")]]],
    )
    t.metadata["caption"] = "T"
    result = render(doc(t))
    assert "\\texttt{x=1}" in result
```

Update ALL existing table tests in `tests/test_latex.py` to use `_cells()` and `_rows()` helpers instead of raw string lists. For example:

```python
# Before:
t = Table(headers=["A", "B"], alignments=["left", "right"], rows=[["1", "2"]])
# After:
t = Table(headers=_cells("A", "B"), alignments=["left", "right"], rows=_rows(["1", "2"]))
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_latex.py -v`

Expected: failures because `render_table()` still calls `escape_latex(h)` on node lists.

**Step 3: Implement changes**

In `src/md_mid/latex.py`, add helper and update `render_table()`:

```python
def _render_nodes(self, nodes: list[Node]) -> str:
    """Render a list of inline nodes (渲染行内节点列表)."""
    return "".join(self.render(n) for n in nodes)
```

Update `render_table()`:

```python
# 表头行 (Header row) — was: escape_latex(h) for h in tbl.headers
header_row = " & ".join(self._render_nodes(h) for h in tbl.headers)

# 数据行 (Data rows) — was: escape_latex(cell) for cell in row
for row in tbl.rows:
    data_row = " & ".join(self._render_nodes(cell) for cell in row)
    lines.append(f"{data_row} \\\\")
```

**Step 4: Run all tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```
feat(latex): render rich inline content in table cells
```

---

## Task 3: Update Markdown Renderer for Rich Table Cells

**Files:**
- Modify: `src/md_mid/markdown.py` — Add HTML cell renderers, update `_render_table()`
- Modify: `tests/test_markdown.py` — Update table tests to use Node cells

**Step 1: Write failing tests**

Add to `tests/test_markdown.py`:

```python
from md_mid.nodes import (
    Table, Text, Strong, Emphasis, CodeInline, MathInline, Link,
)

# 测试辅助函数 (Test helpers for Table cell construction)
def _cells(*texts: str) -> list[list[Node]]:
    """Wrap strings as Text node cells (字符串包装为 Text 节点单元格)."""
    return [[Text(content=t)] for t in texts]

def _rows(*row_texts: list[str]) -> list[list[list[Node]]]:
    """Wrap string rows as Text node rows (字符串行包装为 Text 节点行)."""
    return [[[Text(content=t)] for t in row] for row in row_texts]


class TestTableRichCells:
    def test_bold_in_table_cell(self) -> None:
        """表格粗体 HTML (Bold in table cell renders as <strong>)."""
        t = Table(
            headers=[[Strong(children=[Text(content="H")])]],
            alignments=["left"],
            rows=_rows(["V"]),
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "<strong>H</strong>" in result

    def test_italic_in_table_cell(self) -> None:
        """表格斜体 HTML (Emphasis in table cell renders as <em>)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=[[[Emphasis(children=[Text(content="val")])]]],
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "<em>val</em>" in result

    def test_code_in_table_cell(self) -> None:
        """表格代码 HTML (Code in table cell renders as <code>)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=[[[CodeInline(content="x=1")]]],
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "<code>x=1</code>" in result

    def test_math_in_table_cell(self) -> None:
        """表格数学公式保留 (Math in table cell preserved as $...$)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=[[[MathInline(content="x^2")]]],
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "$x^2$" in result

    def test_text_ampersand_still_escaped(self) -> None:
        """表格纯文本 & 仍被转义 (Plain text & still escaped)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=[[[Text(content="x & y")]]],
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "x &amp; y" in result

    def test_cell_html_injection_escaped(self) -> None:
        """单元格 HTML 注入被转义 (HTML injection in cell is escaped)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=[[[Text(content="<script>alert(1)</script>")]]],
        )
        t.metadata["caption"] = "T"
        result = render(doc(t))
        assert "&lt;script&gt;" in result
        assert "<script>" not in result
```

**安全验收标准 (Security verification criterion):** `_render_cell_html()` 和 `_render_node_html()` 中所有文本输出必须经过 `_esc()`。所有属性值（href、id）必须经过 `_esc()`。恶意输入测试（XSS payload in cell content）必须通过。此规则不可回退。

Update ALL existing table tests in `tests/test_markdown.py` to use `_cells()` and `_rows()` helpers.

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_markdown.py::TestTableRichCells -v`

**Step 3: Implement changes**

In `src/md_mid/markdown.py`, add HTML cell rendering helpers. Add these imports at the top:

```python
from md_mid.nodes import (
    ...,  # existing imports
    Emphasis,
    Strong,
    SoftBreak,
    HardBreak,
)
```

Add cell rendering methods:

```python
def _render_cell_html(self, nodes: list[Node]) -> str:
    """Render inline nodes as HTML for table cell content (表格单元格 HTML 渲染)."""
    return "".join(self._render_node_html(n) for n in nodes)

def _render_node_html(self, node: Node) -> str:
    """Render single inline node as HTML (单个行内节点 HTML 渲染)."""
    if isinstance(node, Text):
        return _esc(node.content)
    if isinstance(node, Strong):
        inner = self._render_cell_html(node.children)
        return f"<strong>{inner}</strong>"
    if isinstance(node, Emphasis):
        inner = self._render_cell_html(node.children)
        return f"<em>{inner}</em>"
    if isinstance(node, CodeInline):
        return f"<code>{_esc(node.content)}</code>"
    if isinstance(node, MathInline):
        return f"${node.content}$"
    if isinstance(node, Link):
        text = self._render_cell_html(node.children)
        return f'<a href="{_esc(node.url)}">{text}</a>'
    if isinstance(node, Citation):
        c = cast(Citation, node)
        refs = "".join(f"[^{key}]" for key in c.keys)
        return f"{_esc(c.display_text)}{refs}" if c.display_text else refs
    if isinstance(node, CrossRef):
        r = cast(CrossRef, node)
        return f'<a href="#{_esc(r.label)}">{_esc(r.display_text)}</a>'
    if isinstance(node, SoftBreak):
        return " "
    if isinstance(node, HardBreak):
        return "<br>"
    # Fallback: render children (回退：渲染子节点)
    return self._render_cell_html(node.children)
```

Update `_render_table()` — replace `_esc(h)` with `self._render_cell_html(h)`:

```python
# 表头 (Table headers) — was: f"<th>{_esc(h)}</th>"
th_cells = "".join(
    f"<th>{self._render_cell_html(h)}</th>" for h in t.headers
)

# 数据行 (Data rows) — was: f"<td>{_esc(cell)}</td>"
for row in t.rows:
    td_cells = "".join(
        f"<td>{self._render_cell_html(cell)}</td>" for cell in row
    )
    data_rows.append(f"      <tr>{td_cells}</tr>")
```

**Step 4: Run all tests**

Run: `uv run pytest -v && make check`

All 209+ tests should pass. E2E tests pass because the parser (Task 1) now produces Node-based cells and renderers handle them.

**Step 5: Commit**

```
feat(markdown): render rich inline content in table cells as HTML
```

---

## Task 4: Fix Nested List Rendering in Markdown

**Files:**
- Modify: `src/md_mid/markdown.py` — Depth-aware list rendering
- Modify: `tests/test_markdown.py` — Nested list tests

**Step 1: Write failing tests**

Add to `tests/test_markdown.py`:

```python
from md_mid.nodes import List, ListItem, Paragraph, Text


class TestNestedList:
    def test_nested_unordered_list(self) -> None:
        """嵌套无序列表缩进 (Nested unordered list is indented)."""
        inner = List(
            ordered=False,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="nested")])])
            ],
        )
        outer = List(
            ordered=False,
            children=[
                ListItem(children=[
                    Paragraph(children=[Text(content="top")]),
                    inner,
                ])
            ],
        )
        result = render(doc(outer))
        lines = result.strip().split("\n")
        # 顶级项无缩进 (Top-level item has no indent)
        assert lines[0].startswith("- top")
        # 嵌套项有缩进 (Nested item is indented)
        nested_line = [l for l in lines if "nested" in l][0]
        assert nested_line.startswith("  - ")

    def test_nested_ordered_list(self) -> None:
        """嵌套有序列表缩进 (Nested ordered list is indented)."""
        inner = List(
            ordered=True,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="sub")])])
            ],
        )
        outer = List(
            ordered=True,
            children=[
                ListItem(children=[
                    Paragraph(children=[Text(content="main")]),
                    inner,
                ])
            ],
        )
        result = render(doc(outer))
        lines = result.strip().split("\n")
        assert lines[0].startswith("1. main")
        nested_line = [l for l in lines if "sub" in l][0]
        assert nested_line.startswith("  ")

    def test_deeply_nested_list(self) -> None:
        """深层嵌套列表 (Deeply nested list has increasing indent)."""
        l3 = List(ordered=False, children=[
            ListItem(children=[Paragraph(children=[Text(content="deep")])])
        ])
        l2 = List(ordered=False, children=[
            ListItem(children=[
                Paragraph(children=[Text(content="mid")]),
                l3,
            ])
        ])
        l1 = List(ordered=False, children=[
            ListItem(children=[
                Paragraph(children=[Text(content="top")]),
                l2,
            ])
        ])
        result = render(doc(l1))
        lines = result.strip().split("\n")
        deep_line = [l for l in lines if "deep" in l][0]
        # 第三层应有 4 个空格缩进 (Level 3 should have 4-space indent)
        assert deep_line.startswith("    - ")

    def test_mixed_ordered_unordered_nesting(self) -> None:
        """混合有序无序嵌套 (Mixed ordered inside unordered)."""
        inner = List(
            ordered=True,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="sub1")])]),
                ListItem(children=[Paragraph(children=[Text(content="sub2")])]),
            ],
        )
        outer = List(
            ordered=False,
            children=[
                ListItem(children=[
                    Paragraph(children=[Text(content="top")]),
                    inner,
                ])
            ],
        )
        result = render(doc(outer))
        assert "- top" in result
        # 嵌套有序列表缩进 (Nested ordered list indented)
        assert "  1." in result

    def test_list_item_with_code_block(self) -> None:
        """列表项含代码块 (List item with code block, indent preserved)."""
        from md_mid.nodes import CodeBlock
        item = ListItem(children=[
            Paragraph(children=[Text(content="example:")]),
            CodeBlock(content="x = 1", language="python"),
        ])
        lst = List(ordered=False, children=[item])
        result = render(doc(lst))
        assert "- example:" in result
        assert "```python" in result
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_markdown.py::TestNestedList -v`

Expected: nested items lack indentation.

**Step 3: Implement changes**

In `src/md_mid/markdown.py`, add `_list_depth` to `__init__`:

```python
def __init__(self, ...) -> None:
    ...
    self._list_depth: int = 0  # 列表嵌套深度 (list nesting depth)
```

Replace `_render_list()`:

```python
def _render_list(self, node: Node) -> str:
    """列表渲染，支持嵌套缩进 (List rendering with nesting indentation)."""
    lst = cast(List, node)
    indent = "  " * self._list_depth
    parts: list[str] = []
    self._list_depth += 1
    for i, item in enumerate(lst.children, start=lst.start):
        marker = f"{i}." if lst.ordered else "-"
        content = self._render_list_item_content(item)
        parts.append(f"{indent}{marker} {content}")
    self._list_depth -= 1
    return "\n".join(parts) + "\n\n"
```

Add `_render_list_item_content()` and update `_render_list_item()`:

```python
def _render_list_item_content(self, node: Node) -> str:
    """列表项内容渲染，嵌套子内容缩进 (List item content with nested indentation)."""
    parts: list[str] = []
    for child in node.children:
        rendered = self._dispatch(child)
        parts.append(rendered)
    result = "".join(parts).strip()
    # 缩进续行到当前列表级别 (Indent continuation lines to current list level)
    lines = result.split("\n")
    if len(lines) > 1:
        indent = "  " * self._list_depth
        result = lines[0] + "\n" + "\n".join(
            indent + line if line.strip() else line
            for line in lines[1:]
        )
    return result

def _render_list_item(self, node: Node) -> str:
    """列表项渲染 (List item rendering)."""
    return self._render_children(node).strip()
```

**Step 4: Run all tests**

Run: `uv run pytest -v && make check`

**Step 5: Commit**

```
feat(markdown): add proper indentation for nested lists
```

---

## Task 5: Configurable Figure/Table Labels (i18n)

**Files:**
- Modify: `src/md_mid/markdown.py` — Add `locale` parameter
- Modify: `src/md_mid/cli.py` — Add `--locale` CLI option
- Modify: `tests/test_markdown.py` — Locale tests
- Modify: `tests/test_cli.py` — CLI locale test

**Step 1: Write failing tests**

In `tests/test_markdown.py`:

```python
class TestLocale:
    def test_english_figure_label(self) -> None:
        """英文图标签 (English figure label: Figure N)."""
        f = Figure(src="a.png", alt="x")
        f.metadata["caption"] = "Cap"
        result = MarkdownRenderer(locale="en").render(doc(f))
        assert "Figure 1" in result

    def test_english_table_label(self) -> None:
        """英文表标签 (English table label: Table N)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=_rows(["V"]),
        )
        t.metadata["caption"] = "Cap"
        result = MarkdownRenderer(locale="en").render(doc(t))
        assert "Table 1" in result

    def test_chinese_is_default(self) -> None:
        """默认中文标签 (Default locale is Chinese)."""
        f = Figure(src="a.png", alt="x")
        f.metadata["caption"] = "Cap"
        result = render(doc(f))
        assert "图 1" in result

    def test_explicit_chinese_locale(self) -> None:
        """显式中文标签 (Explicit zh locale)."""
        t = Table(
            headers=_cells("H"),
            alignments=["left"],
            rows=_rows(["V"]),
        )
        t.metadata["caption"] = "Cap"
        result = MarkdownRenderer(locale="zh").render(doc(t))
        assert "表 1" in result
```

In `tests/test_cli.py`:

```python
def test_markdown_locale_english(tmp_path) -> None:
    """--locale en 使用英文标签 (--locale en uses English labels)."""
    src = tmp_path / "t.mid.md"
    src.write_text(
        "![x](a.png)\n<!-- caption: Cap -->\n"
    )
    out = tmp_path / "out.rendered.md"
    result = CliRunner().invoke(
        main, [str(src), "-t", "markdown", "--locale", "en", "-o", str(out)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "Figure 1" in content
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_markdown.py::TestLocale tests/test_cli.py::test_markdown_locale_english -v`

**Step 3: Implement changes**

In `src/md_mid/markdown.py`, define locale strings and add parameter:

```python
# 标签本地化 (Label localization)
_LABEL_STRINGS: dict[str, dict[str, str]] = {
    "zh": {"figure": "图", "table": "表"},
    "en": {"figure": "Figure", "table": "Table"},
}
```

Add `locale` to `__init__`:

```python
def __init__(
    self,
    bib: dict[str, str] | None = None,
    heading_id_style: str = "attr",
    locale: str = "zh",
    diag: DiagCollector | None = None,
) -> None:
    ...
    self._locale = locale
    self._labels = _LABEL_STRINGS.get(locale, _LABEL_STRINGS["zh"])
```

Replace hardcoded strings in `_render_figure_block()`:

```python
# Was: f"  <figcaption><strong>图 {n}</strong>"
fig_label = self._labels["figure"]
f"  <figcaption><strong>{fig_label} {n}</strong>"
```

Same in `_render_table()`:

```python
# Was: f"  <figcaption><strong>表 {n}</strong>"
tab_label = self._labels["table"]
f"  <figcaption><strong>{tab_label} {n}</strong>"
```

In `src/md_mid/cli.py`, add `--locale` option:

```python
@click.option(
    "--locale",
    type=click.Choice(["zh", "en"]),
    default="zh",
)
```

Pass to `MarkdownRenderer`:

```python
renderer_md = MarkdownRenderer(
    bib=bib,
    heading_id_style=heading_id_style,
    locale=locale,
    diag=diag,
)
```

**Step 4: Run all tests**

Run: `uv run pytest -v && make check`

**Step 5: Commit**

```
feat(markdown,cli): add --locale option for figure/table label language
```

---

## Task 6: CLI stdin/stdout Support

**Files:**
- Modify: `src/md_mid/cli.py` — Accept `-` for stdin, `-o -` for stdout
- Modify: `tests/test_cli.py` — stdin/stdout tests

**Step 1: Write failing tests**

In `tests/test_cli.py`:

```python
def test_stdin_input(tmp_path) -> None:
    """stdin 输入 (Read from stdin with -)."""
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, ["-", "-o", str(out)],
        input="# Hello\n\nWorld.\n",
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\section{Hello}" in content

def test_stdout_output(tmp_path) -> None:
    """stdout 输出 (Write to stdout with -o -)."""
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    result = CliRunner().invoke(main, [str(src), "-o", "-"])
    assert result.exit_code == 0
    assert "\\section{Hello}" in result.output

def test_stdin_stdout_pipe(tmp_path) -> None:
    """stdin→stdout 管道 (stdin to stdout pipe)."""
    result = CliRunner().invoke(
        main, ["-", "-o", "-"],
        input="# Hello\n\nWorld.\n",
    )
    assert result.exit_code == 0
    assert "\\section{Hello}" in result.output

def test_stdout_no_status_message(tmp_path) -> None:
    """-o - 不输出状态信息 (stdout mode suppresses 'Written to...')."""
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    result = CliRunner().invoke(main, [str(src), "-o", "-"])
    assert result.exit_code == 0
    assert "Written to" not in result.output
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_cli.py::test_stdin_input tests/test_cli.py::test_stdout_output -v`

Expected: `-` is not a valid file path.

**Step 3: Implement changes**

In `src/md_mid/cli.py`, change `input` argument to allow `-`:

```python
@click.argument("input", type=click.Path(path_type=Path))  # Remove exists=True
```

Update `main()` function to handle stdin/stdout:

```python
import sys

def main(
    input: Path,
    ...
) -> None:
    """md-mid: 学术写作中间格式转换工具"""
    # 读取输入 (Read input: stdin or file)
    if str(input) == "-":
        text = sys.stdin.read()
        filename = "<stdin>"
    else:
        if not input.exists():
            click.echo(f"Error: Path '{input}' does not exist.", err=True)
            raise SystemExit(2)
        text = input.read_text(encoding="utf-8")
        filename = str(input)

    diag = DiagCollector(filename)
    ...

    # 写入输出 (Write output: stdout or file)
    write_to_stdout = (output is not None and str(output) == "-") or (
        output is None and str(input) == "-"
    )
    if write_to_stdout:
        # stdout 模式不输出状态信息，避免污染管道 (No status message for pipe)
        click.echo(result, nl=False)
    else:
        if output is None:
            output = input.with_suffix(suffix)
        output.write_text(result, encoding="utf-8")
        click.echo(f"Written to {output}")
```

**Step 4: Run all tests**

Run: `uv run pytest -v && make check`

**Step 5: Commit**

```
feat(cli): support stdin (-) input and stdout (-o -) output
```

---

## Task 7: Markdown body/fragment Mode Support

**Files:**
- Modify: `src/md_mid/markdown.py` — Add `mode` parameter
- Modify: `src/md_mid/cli.py` — Pass `mode` to `MarkdownRenderer`
- Modify: `tests/test_markdown.py` — Mode tests

**Step 1: Write failing tests**

In `tests/test_markdown.py`:

```python
class TestMarkdownModes:
    def test_full_mode_has_front_matter(self) -> None:
        """full 模式含前言 (Full mode includes front matter)."""
        d = doc()
        d.metadata["title"] = "Paper"
        d.children = [Paragraph(children=[Text(content="Hello.")])]
        result = MarkdownRenderer(mode="full").render(d)
        assert "---" in result
        assert "title: Paper" in result

    def test_body_mode_no_front_matter(self) -> None:
        """body 模式无前言 (Body mode excludes front matter)."""
        d = doc()
        d.metadata["title"] = "Paper"
        d.children = [Paragraph(children=[Text(content="Hello.")])]
        result = MarkdownRenderer(mode="body").render(d)
        assert "---" not in result
        assert "Hello." in result

    def test_body_mode_has_footnotes(self) -> None:
        """body 模式含脚注 (Body mode includes footnotes)."""
        d = doc(
            Paragraph(children=[
                Citation(keys=["k1"], display_text="A"),
            ])
        )
        result = MarkdownRenderer(mode="body").render(d)
        assert "[^k1]:" in result

    def test_fragment_mode_no_front_matter_no_footnotes(self) -> None:
        """fragment 模式无前言无脚注 (Fragment mode: no FM, no footnotes)."""
        d = doc(
            Paragraph(children=[
                Citation(keys=["k1"], display_text="A"),
            ])
        )
        d.metadata["title"] = "Paper"
        result = MarkdownRenderer(mode="fragment").render(d)
        assert "---" not in result
        assert "[^k1]:" not in result
        # 引用引用仍在正文中 (Citation ref still in body)
        assert "[^k1]" in result
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_markdown.py::TestMarkdownModes -v`

Expected: `MarkdownRenderer` doesn't accept `mode` parameter.

**Step 3: Implement changes**

In `src/md_mid/markdown.py`, add `mode` to `__init__`:

```python
def __init__(
    self,
    bib: dict[str, str] | None = None,
    heading_id_style: str = "attr",
    locale: str = "zh",
    mode: str = "full",
    diag: DiagCollector | None = None,
) -> None:
    ...
    self._mode = mode
```

Update `render()`:

```python
def render(self, doc: Document) -> str:
    self._fig_count = 0
    self._tab_count = 0
    self._list_depth = 0
    self._index = self._build_index(doc)

    parts: list[str] = []

    # full 模式才输出前言 (Only full mode renders front matter)
    if self._mode == "full":
        front_matter = self._render_front_matter(doc)
        if front_matter:
            parts.append(front_matter)

    body = self._render_children(doc)
    parts.append(body)

    # full 和 body 模式输出脚注 (full and body modes render footnotes)
    if self._mode in ("full", "body"):
        footnotes = self._render_footnotes()
        if footnotes:
            parts.append(footnotes)

    return "\n".join(p for p in parts if p)
```

In `src/md_mid/cli.py`, pass `mode` to `MarkdownRenderer`:

```python
renderer_md = MarkdownRenderer(
    bib=bib,
    heading_id_style=heading_id_style,
    locale=locale,
    mode=mode,
    diag=diag,
)
```

**Step 4: Run all tests**

Run: `uv run pytest -v && make check`

**Step 5: Commit**

```
feat(markdown,cli): support body/fragment modes for Markdown output
```

---

## Execution Order

```
Task 1 (Node + Parser)  ──→ Task 2 (LaTeX table) ──→ Task 3 (MD table)
                              ↓                         ↓
                         (independent from here)   (independent from here)
Task 4 (Nested lists)   ── independent
Task 5 (Locale labels)  ── independent
Task 6 (stdin/stdout)   ── independent
Task 7 (MD mode)        ── independent (but depends on Task 5 if locale param added first)
```

**Recommended order:** 1 → 2 → 3 → 4 → 5 → 6 → 7

Tasks 4–7 can be parallelized after Task 3 completes.

---

## Verification

After all tasks:
1. `uv run pytest -v --tb=short` — 全量测试通过，新增测试覆盖所有关键场景
2. `uv run ruff check src/ tests/` — 0 errors
3. `uv run mypy src/md_mid/` — 0 errors（scope: 源代码，不含 tests）
4. Manual: Create table with `**bold**` and `$x^2$` cells → verify both renderers preserve formatting
5. Manual: Create nested list → verify Markdown has proper indentation
6. Manual: `echo "# Hello" | uv run md-mid - -o -` → LaTeX on stdout, no "Written to" message
7. Manual: `uv run md-mid test.mid.md -t markdown --locale en` → "Figure 1" / "Table 1"
8. Manual: `uv run md-mid test.mid.md -t markdown --mode body` → no front matter
9. Security: table cell with `<script>alert(1)</script>` content → escaped in both renderers

---

## Post-Execution Checklist

执行完毕后需同步更新的文档：

- [ ] **PRD §11**: 更新 Table 节点定义 (`headers: string[]` → `headers: CellContent[]`)
- [ ] **PRD §9**: CLI 帮助菜单补充 `--locale`、stdin (`-`)、stdout (`-o -`) 用法
- [ ] **PRD §3.1/3.2**: 将 `--mode` 从 LaTeX Options 提升为通用 Output Options，补充 Markdown 模式语义
- [ ] **Phase 2 researcher notes**: 更新 Table cell 相关的渲染方法描述
