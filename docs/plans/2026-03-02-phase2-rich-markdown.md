# Phase 2: Rich Markdown MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Rich Markdown renderer that converts EAST → GitHub/Obsidian/Typora-readable Markdown with HTML extensions for citations, cross-references, figures, and tables.

**Architecture:** Two-pass design — Pass 1 (IndexPass) collects all citation keys; Pass 2 (RenderPass) renders using the index. A fresh `MarkdownRenderer` class in `src/md_mid/markdown.py` mirrors `LaTeXRenderer` in structure. The CLI gains `-t markdown` support with `--bib` and `--heading-id-style` options.

**Tech Stack:** Python 3.11+, ruamel.yaml (already installed), click (already installed), standard library `re` for BibTeX parsing.

---

## Key Design Decisions

Before implementing, understand these decisions:

1. **Two-pass is required** because citation footnote definitions must appear at the *end* of the document, but citations appear throughout. Pass 1 collects all cite keys in order; Pass 2 renders them as `[^key]` references and appends definitions at the end.

2. **Figure numbering uses a running counter in Pass 2**, not Pass 1. Sequential numbers (`图 1`, `图 2`) are assigned as figures are encountered during rendering — no pre-scan needed. Pass 1 only collects citation keys.

3. **Image-in-Paragraph detection**: The parser creates `Image` nodes inside `Paragraph` wrappers. The comment processor attaches `caption`/`label` metadata to the `Image` node directly (via paragraph penetration). The markdown renderer must detect this pattern and render it as an HTML figure block. A "figure context" = `Figure` node OR `Paragraph(children=[Image])` where Image has `caption` or `label` metadata.

4. **Inline elements join without separators** — the parent block node controls newlines. Block nodes add their own trailing `\n\n`.

5. **No LaTeX escaping** — markdown output must not escape special chars. Text is output as-is (except HTML-reserved chars `<`, `>`, `&` in non-code contexts).

---

## Task 1: MarkdownRenderer Skeleton + Basic Inline/Block Nodes

**Files:**
- Create: `src/md_mid/markdown.py`
- Create: `tests/test_markdown.py`

**Step 1: Write failing tests**

```python
# tests/test_markdown.py
from md_mid.markdown import MarkdownRenderer
from md_mid.nodes import (
    Blockquote,
    CodeBlock,
    CodeInline,
    Document,
    Emphasis,
    HardBreak,
    Heading,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    SoftBreak,
    Strong,
    Text,
    ThematicBreak,
)


def render(node, **kwargs):
    return MarkdownRenderer(**kwargs).render(node)


def doc(*children):
    return Document(children=list(children))


class TestInline:
    def test_text(self):
        assert render(doc(Paragraph(children=[Text(content="hello")]))) == "hello\n\n"

    def test_strong(self):
        p = Paragraph(children=[Strong(children=[Text(content="bold")])])
        assert "**bold**" in render(doc(p))

    def test_emphasis(self):
        p = Paragraph(children=[Emphasis(children=[Text(content="italic")])])
        assert "*italic*" in render(doc(p))

    def test_code_inline(self):
        p = Paragraph(children=[CodeInline(content="x = 1")])
        assert "`x = 1`" in render(doc(p))

    def test_math_inline(self):
        p = Paragraph(children=[MathInline(content=r"E=mc^2")])
        assert "$E=mc^2$" in render(doc(p))

    def test_softbreak(self):
        p = Paragraph(children=[Text(content="a"), SoftBreak(), Text(content="b")])
        result = render(doc(p))
        assert "a\nb" in result

    def test_hardbreak(self):
        p = Paragraph(children=[Text(content="a"), HardBreak(), Text(content="b")])
        result = render(doc(p))
        assert "a  \nb" in result


class TestBlock:
    def test_heading_level1(self):
        h = Heading(level=1, children=[Text(content="Title")])
        assert "# Title" in render(doc(h))

    def test_heading_level2(self):
        h = Heading(level=2, children=[Text(content="Sec")])
        assert "## Sec" in render(doc(h))

    def test_paragraph(self):
        p = Paragraph(children=[Text(content="Hello.")])
        result = render(doc(p))
        assert "Hello." in result
        assert result.endswith("\n\n") or result.endswith("\n")

    def test_code_block(self):
        c = CodeBlock(content="x = 1", language="python")
        result = render(doc(c))
        assert "```python" in result
        assert "x = 1" in result
        assert "```" in result

    def test_math_block(self):
        m = MathBlock(content=r"x^2 + y^2 = z^2")
        result = render(doc(m))
        assert "$$" in result
        assert r"x^2 + y^2 = z^2" in result

    def test_unordered_list(self):
        lst = List(
            ordered=False,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="a")])]),
                ListItem(children=[Paragraph(children=[Text(content="b")])]),
            ],
        )
        result = render(doc(lst))
        assert "- a" in result
        assert "- b" in result

    def test_ordered_list(self):
        lst = List(
            ordered=True,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="x")])]),
            ],
        )
        result = render(doc(lst))
        assert "1. x" in result

    def test_blockquote(self):
        bq = Blockquote(children=[Paragraph(children=[Text(content="quote")])])
        result = render(doc(bq))
        assert "> quote" in result

    def test_thematic_break(self):
        result = render(doc(ThematicBreak()))
        assert "---" in result
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_markdown.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'md_mid.markdown'`

**Step 3: Create `src/md_mid/markdown.py`**

```python
"""Rich Markdown Renderer: EAST → GitHub/Obsidian/Typora-compatible Markdown.

两次扫描架构 (Two-pass architecture):
  Pass 1 (Index): 预扫描，收集引用键 (Pre-scan to collect cite keys)
  Pass 2 (Render): 使用索引数据渲染 (Render using index data)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from md_mid.diagnostic import DiagCollector
from md_mid.nodes import (
    Blockquote,
    Citation,
    CodeBlock,
    CodeInline,
    CrossRef,
    Document,
    Emphasis,
    Environment,
    Figure,
    FootnoteDef,
    FootnoteRef,
    HardBreak,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    RawBlock,
    SoftBreak,
    Strong,
    Table,
    Text,
    ThematicBreak,
)


@dataclass
class MarkdownIndex:
    """Pass 1 收集结果 (Pass 1 results)."""

    cite_keys: list[str] = field(default_factory=list)  # 按出现顺序排列 (ordered unique keys)


class MarkdownRenderer:
    """EAST → Rich Markdown 渲染器 (EAST to Rich Markdown renderer)."""

    def __init__(
        self,
        bib: dict[str, str] | None = None,
        heading_id_style: str = "attr",
        diag: DiagCollector | None = None,
    ) -> None:
        """初始化渲染器 (Initialize renderer).

        Args:
            bib: BibTeX key → formatted citation string (BibTeX 键 → 格式化引用字符串)
            heading_id_style: Anchor style for headings: 'attr' ({#id}) or 'html' (<hN id=...>)
                             标题锚点风格
            diag: Optional diagnostic collector (可选诊断收集器)
        """
        self._bib = bib or {}
        self._heading_id_style = heading_id_style
        self._diag = diag or DiagCollector("unknown")
        self._index: MarkdownIndex = MarkdownIndex()
        self._fig_count: int = 0  # 图计数器 (figure counter)
        self._tab_count: int = 0  # 表计数器 (table counter)

    def render(self, doc: Document) -> str:
        """渲染文档为 Rich Markdown (Render document to Rich Markdown).

        Args:
            doc: EAST Document node (EAST 文档节点)

        Returns:
            Rich Markdown string (Rich Markdown 字符串)
        """
        # 重置计数器 (Reset counters for fresh render)
        self._fig_count = 0
        self._tab_count = 0

        # Pass 1: 收集引用键 (Collect citation keys)
        self._index = self._build_index(doc)

        # Pass 2: 渲染 (Render)
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

    # ── Pass 1: Index ────────────────────────────────────────────────────────

    def _build_index(self, root: Node) -> MarkdownIndex:
        """构建索引 (Build index from tree walk)."""
        index = MarkdownIndex()
        self._index_node(root, index)
        return index

    def _index_node(self, node: Node, index: MarkdownIndex) -> None:
        """递归收集引用键 (Recursively collect citation keys)."""
        if isinstance(node, Citation):
            for key in node.keys:
                if key not in index.cite_keys:
                    index.cite_keys.append(key)
        for child in node.children:
            self._index_node(child, index)

    # ── Pass 2: Render helpers ───────────────────────────────────────────────

    def _dispatch(self, node: Node) -> str:
        """分发到对应渲染方法 (Dispatch to node-specific render method)."""
        method_name = f"_render_{node.type}"
        method = getattr(self, method_name, None)
        if method is None:
            self._diag.warning(f"Unhandled node type '{node.type}', rendering children only")
            return self._render_children(node)
        return method(node)

    def _render_children(self, node: Node) -> str:
        """渲染所有子节点并拼接 (Render and concatenate all children)."""
        return "".join(self._dispatch(c) for c in node.children)

    # ── Front matter & footnotes ─────────────────────────────────────────────

    def _render_front_matter(self, doc: Document) -> str:
        """文档级指令 → YAML front matter (Document directives → YAML front matter)."""
        keys = ["title", "author", "date", "abstract"]
        lines: list[str] = []
        for key in keys:
            val = doc.metadata.get(key)
            if val is not None:
                lines.append(f"{key}: {val}")
        if not lines:
            return ""
        return "---\n" + "\n".join(lines) + "\n---\n"

    def _render_footnotes(self) -> str:
        """渲染脚注定义 (Render footnote definitions at end of document)."""
        if not self._index.cite_keys:
            return ""
        defs: list[str] = []
        for key in self._index.cite_keys:
            content = self._bib.get(key, key)
            defs.append(f"[^{key}]: {content}")
        return "\n".join(defs) + "\n"

    # ── Block nodes ──────────────────────────────────────────────────────────

    def _render_document(self, node: Document) -> str:
        """渲染文档（由 render() 直接调用，不通过 _dispatch）."""
        return self._render_children(node)

    def _render_heading(self, node: Node) -> str:
        """标题渲染 (Heading rendering)."""
        h = cast(Heading, node)
        prefix = "#" * h.level
        text = self._render_children(h)
        label = str(h.metadata.get("label", ""))
        if label:
            if self._heading_id_style == "html":
                return f"<h{h.level} id=\"{label}\">{text}</h{h.level}>\n\n"
            else:
                # attr style: ## Heading {#id}
                return f"{prefix} {text} {{#{label}}}\n\n"
        return f"{prefix} {text}\n\n"

    def _render_paragraph(self, node: Node) -> str:
        """段落渲染，检测图片上下文 (Paragraph rendering, detect figure context)."""
        p = cast(Paragraph, node)
        # 图片段落穿透 (Image-in-paragraph figure promotion)
        if len(p.children) == 1 and isinstance(p.children[0], Image):
            img = cast(Image, p.children[0])
            if "caption" in img.metadata or "label" in img.metadata:
                return self._render_image_as_figure(img) + "\n\n"
        return self._render_children(p) + "\n\n"

    def _render_blockquote(self, node: Node) -> str:
        """引用块渲染 (Blockquote rendering)."""
        inner = self._render_children(node).strip()
        lines = inner.split("\n")
        return "\n".join(f"> {line}" for line in lines) + "\n\n"

    def _render_list(self, node: Node) -> str:
        """列表渲染 (List rendering)."""
        lst = cast(List, node)
        parts: list[str] = []
        for i, item in enumerate(lst.children, start=lst.start):
            marker = f"{i}." if lst.ordered else "-"
            content = self._dispatch(item).strip()
            parts.append(f"{marker} {content}")
        return "\n".join(parts) + "\n\n"

    def _render_list_item(self, node: Node) -> str:
        """列表项渲染 (List item rendering)."""
        return self._render_children(node).strip()

    def _render_code_block(self, node: Node) -> str:
        """代码块渲染 (Code block rendering)."""
        c = cast(CodeBlock, node)
        lang = c.language or ""
        return f"```{lang}\n{c.content}\n```\n\n"

    def _render_math_block(self, node: Node) -> str:
        """数学块渲染 (Math block rendering)."""
        m = cast(MathBlock, node)
        label = str(m.metadata.get("label", ""))
        anchor = f'<a id="{label}"></a>\n' if label else ""
        return f"{anchor}$$\n{m.content}\n$$\n\n"

    def _render_figure(self, node: Node) -> str:
        """Figure 节点渲染 (Figure node rendering)."""
        f = cast(Figure, node)
        return self._render_figure_block(f.src, f.alt, f.metadata) + "\n\n"

    def _render_image(self, node: Node) -> str:
        """普通行内图片渲染 (Plain inline image rendering)."""
        img = cast(Image, node)
        return f"![{img.alt}]({img.src})"

    def _render_image_as_figure(self, img: Image) -> str:
        """将 Image 节点渲染为 HTML figure 块 (Render Image as HTML figure block)."""
        return self._render_figure_block(img.src, img.alt, img.metadata)

    def _render_figure_block(
        self,
        src: str,
        alt: str,
        metadata: dict[str, object],
    ) -> str:
        """生成 HTML figure 块 (Generate HTML figure block)."""
        self._fig_count += 1
        n = self._fig_count
        label = str(metadata.get("label", ""))
        caption = str(metadata.get("caption", ""))
        id_attr = f' id="{label}"' if label else ""
        lines: list[str] = [
            f'<figure{id_attr}>',
            f'  <img src="{src}" alt="{alt}" style="max-width:100%">',
        ]
        if caption:
            lines.append(f"  <figcaption><strong>图 {n}</strong>: {caption}</figcaption>")
        else:
            lines.append(f"  <figcaption><strong>图 {n}</strong></figcaption>")

        # AI 信息折叠块 (AI info details block)
        ai = metadata.get("ai")
        if isinstance(ai, dict):
            lines.append("  <details>")
            lines.append("    <summary>🎨 AI Generation Info</summary>")
            if model := ai.get("model"):
                lines.append(f"    <p><strong>Model</strong>: {model}</p>")
            if prompt := ai.get("prompt"):
                lines.append(f"    <p><strong>Prompt</strong>: {prompt}</p>")
            if neg := ai.get("negative_prompt"):
                lines.append(f"    <p><strong>Negative</strong>: {neg}</p>")
            if params := ai.get("params"):
                lines.append(f"    <p><strong>Params</strong>: {params}</p>")
            lines.append("  </details>")

        lines.append("</figure>")
        return "\n".join(lines)

    def _render_table(self, node: Node) -> str:
        """表格渲染为 HTML table + caption (Table rendering as HTML table with caption)."""
        t = cast(Table, node)
        self._tab_count += 1
        n = self._tab_count
        label = str(t.metadata.get("label", ""))
        caption = str(t.metadata.get("caption", ""))
        id_attr = f' id="{label}"' if label else ""

        # 表头 (Table headers)
        th_cells = "".join(f"<th>{h}</th>" for h in t.headers)
        header_row = f"      <tr>{th_cells}</tr>"

        # 数据行 (Data rows)
        data_rows: list[str] = []
        for row in t.rows:
            td_cells = "".join(f"<td>{cell}</td>" for cell in row)
            data_rows.append(f"      <tr>{td_cells}</tr>")

        lines: list[str] = [
            f'<figure{id_attr}>',
            "  <table>",
            "    <thead>",
            header_row,
            "    </thead>",
            "    <tbody>",
            *data_rows,
            "    </tbody>",
            "  </table>",
        ]
        if caption:
            lines.append(f"  <figcaption><strong>表 {n}</strong>: {caption}</figcaption>")
        else:
            lines.append(f"  <figcaption><strong>表 {n}</strong></figcaption>")
        lines.append("</figure>")
        return "\n".join(lines) + "\n\n"

    def _render_environment(self, node: Node) -> str:
        """环境节点渲染（直接渲染内容）(Environment: render children)."""
        return self._render_children(node)

    def _render_raw_block(self, node: Node) -> str:
        """原始 LaTeX 块 → 折叠块 (Raw LaTeX block → details fold)."""
        rb = cast(RawBlock, node)
        return (
            "<details>\n"
            "<summary>📄 Raw LaTeX</summary>\n\n"
            f"```latex\n{rb.content}\n```\n\n"
            "</details>\n\n"
        )

    def _render_thematic_break(self, node: Node) -> str:
        """分隔线渲染 (Thematic break rendering)."""
        return "---\n\n"

    # ── Inline nodes ─────────────────────────────────────────────────────────

    def _render_text(self, node: Node) -> str:
        """文本渲染 (Text rendering)."""
        return cast(Text, node).content

    def _render_strong(self, node: Node) -> str:
        """加粗渲染 (Bold rendering)."""
        return f"**{self._render_children(node)}**"

    def _render_emphasis(self, node: Node) -> str:
        """斜体渲染 (Italic rendering)."""
        return f"*{self._render_children(node)}*"

    def _render_code_inline(self, node: Node) -> str:
        """行内代码渲染 (Inline code rendering)."""
        return f"`{cast(CodeInline, node).content}`"

    def _render_math_inline(self, node: Node) -> str:
        """行内公式渲染 (Inline math rendering)."""
        return f"${cast(MathInline, node).content}$"

    def _render_link(self, node: Node) -> str:
        """链接渲染 (Link rendering)."""
        lnk = cast(Link, node)
        text = self._render_children(lnk)
        return f"[{text}]({lnk.url})"

    def _render_citation(self, node: Node) -> str:
        """引用渲染 → Markdown 脚注 (Citation → Markdown footnote reference)."""
        c = cast(Citation, node)
        refs = "".join(f"[^{key}]" for key in c.keys)
        if c.display_text:
            return f"{c.display_text}{refs}"
        return refs

    def _render_cross_ref(self, node: Node) -> str:
        """交叉引用 → HTML 锚点 (Cross-reference → HTML anchor link)."""
        r = cast(CrossRef, node)
        return f'<a href="#{r.label}">{r.display_text}</a>'

    def _render_softbreak(self, node: Node) -> str:
        """软换行 (Soft break)."""
        return "\n"

    def _render_hardbreak(self, node: Node) -> str:
        """硬换行 (Hard break — two trailing spaces + newline)."""
        return "  \n"

    def _render_footnote_ref(self, node: Node) -> str:
        """脚注引用渲染 (Footnote reference rendering)."""
        fr = cast(FootnoteRef, node)
        return f"[^{fr.ref_id}]"

    def _render_footnote_def(self, node: Node) -> str:
        """脚注定义渲染（跳过，集中输出到末尾）(Footnote def — skipped, output at end)."""
        return ""
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_markdown.py -v
```

Expected: all TestInline and TestBlock tests pass.

**Step 5: Verify quality**

```bash
uv run ruff check src/md_mid/markdown.py tests/test_markdown.py
uv run mypy src/md_mid/markdown.py
```

Expected: 0 errors each.

**Step 6: Commit**

```bash
git add src/md_mid/markdown.py tests/test_markdown.py
git commit -m "feat(markdown): add MarkdownRenderer skeleton with two-pass architecture"
```

---

## Task 2: CrossRef + Heading Labels

`_render_cross_ref` and `_render_heading` with labels are already implemented in Task 1. This task adds the tests to verify correctness.

**Files:**
- Modify: `tests/test_markdown.py` — add `TestCrossRef` and `TestHeadingLabel` classes

**Step 1: Add tests**

```python
# Add to tests/test_markdown.py

from md_mid.nodes import CrossRef, Link


class TestCrossRef:
    def test_cross_ref_html_anchor(self):
        r = CrossRef(label="fig:result", display_text="图1")
        p = Paragraph(children=[r])
        result = render(doc(p))
        assert '<a href="#fig:result">图1</a>' in result

    def test_cross_ref_in_sentence(self):
        p = Paragraph(children=[
            Text(content="如"),
            CrossRef(label="fig:a", display_text="图1"),
            Text(content="所示"),
        ])
        result = render(doc(p))
        assert '如<a href="#fig:a">图1</a>所示' in result


class TestHeadingLabel:
    def test_heading_with_label_attr_style(self):
        h = Heading(level=2, children=[Text(content="方法")])
        h.metadata["label"] = "sec:method"
        result = render(doc(h))
        assert "## 方法 {#sec:method}" in result

    def test_heading_with_label_html_style(self):
        h = Heading(level=2, children=[Text(content="方法")])
        h.metadata["label"] = "sec:method"
        result = render(doc(h), heading_id_style="html")
        assert '<h2 id="sec:method">方法</h2>' in result

    def test_heading_without_label(self):
        h = Heading(level=1, children=[Text(content="Title")])
        result = render(doc(h))
        assert "# Title" in result
        assert "{#" not in result
        assert "<h1" not in result

    def test_math_block_with_label_gets_anchor(self):
        m = MathBlock(content=r"E=mc^2")
        m.metadata["label"] = "eq:einstein"
        result = render(doc(m))
        assert '<a id="eq:einstein"></a>' in result
        assert "$$" in result
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_markdown.py::TestCrossRef tests/test_markdown.py::TestHeadingLabel -v
```

Expected: all 5 tests pass.

**Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test(markdown): add cross-ref and heading label tests"
```

---

## Task 3: Citation → Markdown Footnotes

`_render_citation` and `_render_footnotes` are already implemented. This task tests them end-to-end.

**Files:**
- Modify: `tests/test_markdown.py` — add `TestCitation` class

**Step 1: Add tests**

```python
# Add to tests/test_markdown.py

from md_mid.nodes import Citation


class TestCitation:
    def test_single_cite_with_display(self):
        c = Citation(keys=["wang2024"], display_text="Wang et al.")
        p = Paragraph(children=[c])
        result = render(doc(p))
        assert "Wang et al.[^wang2024]" in result

    def test_single_cite_empty_display(self):
        c = Citation(keys=["wang2024"], display_text="")
        p = Paragraph(children=[c])
        result = render(doc(p))
        assert "[^wang2024]" in result

    def test_multiple_keys(self):
        c = Citation(keys=["a", "b", "c"], display_text="1-3")
        p = Paragraph(children=[c])
        result = render(doc(p))
        assert "1-3[^a][^b][^c]" in result

    def test_footnote_definitions_appear_at_end(self):
        c = Citation(keys=["wang2024"], display_text="Wang")
        p = Paragraph(children=[c])
        result = render(doc(p))
        body_pos = result.find("Wang[^wang2024]")
        def_pos = result.find("[^wang2024]:", body_pos)
        assert def_pos > body_pos, "Footnote definition should appear after citation reference"

    def test_footnote_definition_content_key_only(self):
        """Without .bib, footnote definition contains just the key (无 .bib 时，脚注定义仅含键名)."""
        c = Citation(keys=["li2023"], display_text="Li")
        p = Paragraph(children=[c])
        result = render(doc(p))
        assert "[^li2023]: li2023" in result

    def test_footnote_definition_from_bib(self):
        """With .bib dict, footnote definition uses formatted entry (有 .bib 时使用格式化条目)."""
        c = Citation(keys=["wang2024"], display_text="Wang")
        p = Paragraph(children=[c])
        bib = {"wang2024": "Wang et al. Point Cloud Registration. CVPR, 2024."}
        result = render(doc(p), bib=bib)
        assert "[^wang2024]: Wang et al. Point Cloud Registration. CVPR, 2024." in result

    def test_cite_keys_ordered_in_footnotes(self):
        """Footnote definitions appear in cite order (脚注定义按引用顺序出现)."""
        p = Paragraph(children=[
            Citation(keys=["a"], display_text="A"),
            Text(content=" and "),
            Citation(keys=["b"], display_text="B"),
        ])
        result = render(doc(p))
        pos_a = result.find("[^a]: a")
        pos_b = result.find("[^b]: b")
        assert pos_a < pos_b
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_markdown.py::TestCitation -v
```

Expected: all 7 tests pass.

**Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test(markdown): add citation footnote tests"
```

---

## Task 4: Figure/Image → HTML Figure Block with Auto-Numbering

`_render_figure_block` and `_render_paragraph` (with figure detection) are already implemented. This task tests them.

**Files:**
- Modify: `tests/test_markdown.py` — add `TestFigure` class

**Step 1: Add tests**

```python
# Add to tests/test_markdown.py

from md_mid.nodes import Figure, Image


class TestFigure:
    def test_figure_node_renders_html_block(self):
        f = Figure(src="fig.png", alt="alt text")
        f.metadata["caption"] = "My Fig"
        f.metadata["label"] = "fig:a"
        result = render(doc(f))
        assert '<figure id="fig:a">' in result
        assert '<img src="fig.png" alt="alt text"' in result
        assert "<figcaption><strong>图 1</strong>: My Fig</figcaption>" in result
        assert "</figure>" in result

    def test_image_in_paragraph_promoted_to_figure(self):
        img = Image(src="img.png", alt="photo")
        img.metadata["caption"] = "Photo"
        img.metadata["label"] = "fig:photo"
        p = Paragraph(children=[img])
        result = render(doc(p))
        assert '<figure id="fig:photo">' in result
        assert "Photo" in result

    def test_plain_image_not_promoted(self):
        """Image without caption/label stays inline (无 caption/label 的图片保持行内)."""
        img = Image(src="img.png", alt="plain")
        p = Paragraph(children=[img])
        result = render(doc(p))
        assert "![plain](img.png)" in result
        assert "<figure" not in result

    def test_figure_auto_numbering(self):
        f1 = Figure(src="a.png", alt="")
        f1.metadata["caption"] = "First"
        f1.metadata["label"] = "fig:first"
        f2 = Figure(src="b.png", alt="")
        f2.metadata["caption"] = "Second"
        f2.metadata["label"] = "fig:second"
        result = render(doc(f1, f2))
        assert "图 1" in result
        assert "图 2" in result
        # Order matters
        pos1 = result.find("图 1")
        pos2 = result.find("图 2")
        assert pos1 < pos2

    def test_figure_without_label_no_id(self):
        f = Figure(src="a.png", alt="")
        f.metadata["caption"] = "No label"
        result = render(doc(f))
        assert "id=" not in result
        assert "<figure>" in result

    def test_figure_with_ai_info(self):
        f = Figure(src="ai.png", alt="AI fig")
        f.metadata["caption"] = "AI Generated"
        f.metadata["label"] = "fig:ai"
        f.metadata["ai"] = {
            "model": "dall-e-3",
            "prompt": "Academic diagram",
            "negative_prompt": "photorealistic",
        }
        result = render(doc(f))
        assert "<details>" in result
        assert "🎨 AI Generation Info" in result
        assert "dall-e-3" in result
        assert "Academic diagram" in result
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_markdown.py::TestFigure -v
```

Expected: all 6 tests pass.

**Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test(markdown): add figure rendering tests"
```

---

## Task 5: Table → HTML Table + Caption + Auto-Numbering

`_render_table` is already implemented. Add tests.

**Files:**
- Modify: `tests/test_markdown.py` — add `TestTable` class

**Step 1: Add tests**

```python
# Add to tests/test_markdown.py

from md_mid.nodes import Table


class TestTable:
    def test_basic_table(self):
        t = Table(
            headers=["Method", "RMSE"],
            alignments=["left", "left"],
            rows=[["RANSAC", "2.3"], ["Ours", "1.9"]],
        )
        t.metadata["caption"] = "Results"
        t.metadata["label"] = "tab:results"
        result = render(doc(t))
        assert '<figure id="tab:results">' in result
        assert "<table>" in result
        assert "<th>Method</th>" in result
        assert "<td>RANSAC</td>" in result
        assert "<figcaption><strong>表 1</strong>: Results</figcaption>" in result
        assert "</table>" in result
        assert "</figure>" in result

    def test_table_auto_numbering(self):
        t1 = Table(headers=["A"], alignments=["left"], rows=[["1"]])
        t1.metadata["caption"] = "First table"
        t1.metadata["label"] = "tab:first"
        t2 = Table(headers=["B"], alignments=["left"], rows=[["2"]])
        t2.metadata["caption"] = "Second table"
        t2.metadata["label"] = "tab:second"
        result = render(doc(t1, t2))
        assert "表 1" in result
        assert "表 2" in result

    def test_table_and_figure_numbered_separately(self):
        """Figures and tables use independent counters (图和表使用独立计数器)."""
        f = Figure(src="a.png", alt="")
        f.metadata["caption"] = "A figure"
        t = Table(headers=["X"], alignments=["left"], rows=[["y"]])
        t.metadata["caption"] = "A table"
        result = render(doc(f, t))
        assert "图 1" in result
        assert "表 1" in result
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_markdown.py::TestTable -v
```

Expected: all 3 tests pass.

**Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test(markdown): add table rendering tests"
```

---

## Task 6: RawBlock → Details + Document → YAML Front Matter

Both `_render_raw_block` and `_render_front_matter` are already implemented. Add tests.

**Files:**
- Modify: `tests/test_markdown.py` — add `TestRawBlock` and `TestFrontMatter` classes

**Step 1: Add tests**

```python
# Add to tests/test_markdown.py

from md_mid.nodes import RawBlock


class TestRawBlock:
    def test_raw_block_renders_details(self):
        rb = RawBlock(content=r"\newcommand{\myop}{\operatorname}")
        result = render(doc(rb))
        assert "<details>" in result
        assert "📄 Raw LaTeX" in result
        assert "```latex" in result
        assert r"\newcommand{\myop}{\operatorname}" in result
        assert "</details>" in result

    def test_raw_block_content_preserved(self):
        content = r"\begin{algorithm}" + "\nStep 1\n" + r"\end{algorithm}"
        rb = RawBlock(content=content)
        result = render(doc(rb))
        assert content in result


class TestFrontMatter:
    def test_front_matter_with_title_author(self):
        d = doc()
        d.metadata["title"] = "My Paper"
        d.metadata["author"] = "Alice"
        result = render(d)
        assert "---" in result
        assert "title: My Paper" in result
        assert "author: Alice" in result

    def test_front_matter_appears_first(self):
        d = Document(children=[Paragraph(children=[Text(content="Body.")])])
        d.metadata["title"] = "Title"
        result = render(d)
        fm_pos = result.find("title: Title")
        body_pos = result.find("Body.")
        assert fm_pos < body_pos

    def test_no_front_matter_when_no_metadata(self):
        d = Document(children=[Paragraph(children=[Text(content="Body.")])])
        result = render(d)
        assert "---" not in result
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_markdown.py::TestRawBlock tests/test_markdown.py::TestFrontMatter -v
```

Expected: all 5 tests pass.

**Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test(markdown): add raw block and front matter tests"
```

---

## Task 7: BibTeX Minimal Parser

Create `src/md_mid/bibtex.py` with a minimal parser for extracting citation metadata from `.bib` files.

**Files:**
- Create: `src/md_mid/bibtex.py`
- Create: `tests/test_bibtex.py`

**Step 1: Write failing tests**

```python
# tests/test_bibtex.py
from md_mid.bibtex import parse_bib


BIB_CONTENT = r"""
@article{wang2024,
  author = {Wang, Alice and Li, Bob},
  title  = {Point Cloud Registration via 4PCS},
  journal = {CVPR},
  year   = {2024},
}

@inproceedings{fischler1981,
  author = {Fischler, M. A. and Bolles, R. C.},
  title  = {Random Sample Consensus},
  booktitle = {CACM},
  year   = {1981},
}

@book{goossens1993,
  author = {Goossens, Michel},
  title  = {The LaTeX Companion},
  year   = {1993},
}
"""


def test_parse_returns_dict():
    result = parse_bib(BIB_CONTENT)
    assert isinstance(result, dict)
    assert "wang2024" in result
    assert "fischler1981" in result


def test_parse_article_formatted():
    result = parse_bib(BIB_CONTENT)
    entry = result["wang2024"]
    assert "Wang" in entry
    assert "2024" in entry
    assert "Point Cloud Registration" in entry


def test_parse_inproceedings():
    result = parse_bib(BIB_CONTENT)
    entry = result["fischler1981"]
    assert "Fischler" in entry
    assert "1981" in entry


def test_missing_key_not_in_result():
    result = parse_bib(BIB_CONTENT)
    assert "nonexistent" not in result


def test_empty_bib_returns_empty_dict():
    assert parse_bib("") == {}
    assert parse_bib("  ") == {}
```

**Step 2: Run to verify fails**

```bash
uv run pytest tests/test_bibtex.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'md_mid.bibtex'`

**Step 3: Create `src/md_mid/bibtex.py`**

```python
"""最小化 BibTeX 解析器：从 .bib 文件提取引用信息供 Rich Markdown 脚注使用。

Minimal BibTeX parser for extracting citation metadata for Rich Markdown footnotes.
仅支持常见字段（author, title, journal/booktitle, year）的提取与格式化。
Only extracts and formats common fields: author, title, journal/booktitle, year.
"""

from __future__ import annotations

import re

# 匹配 @type{key, ...} 条目 (Match @type{key, ...} entries)
_ENTRY_RE = re.compile(
    r"@\w+\{(\w+)\s*,([^@]*)\}",
    re.DOTALL | re.IGNORECASE,
)

# 匹配 field = {value} 或 field = "value" 或 field = bare
# (Match field = {value}, field = "value", or field = bare)
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|\"([^\"]*)\"|(\S[^,\n]*))",
    re.DOTALL,
)


def parse_bib(bib_text: str) -> dict[str, str]:
    """解析 .bib 文件内容，返回 key → 格式化引用字符串的映射。

    Parse .bib file content, return key → formatted citation string mapping.

    Args:
        bib_text: Raw .bib file content (.bib 文件原始内容)

    Returns:
        Dict mapping cite key → one-line citation string (引用键 → 单行引用字符串的字典)
    """
    result: dict[str, str] = {}
    for entry_match in _ENTRY_RE.finditer(bib_text):
        key = entry_match.group(1).strip()
        fields_text = entry_match.group(2)
        fields = _extract_fields(fields_text)
        result[key] = _format_entry(fields)
    return result


def _extract_fields(fields_text: str) -> dict[str, str]:
    """提取条目中的所有字段 (Extract all fields from entry text)."""
    fields: dict[str, str] = {}
    for m in _FIELD_RE.finditer(fields_text):
        field_name = m.group(1).lower()
        # 取三个可能的捕获组中第一个非 None 的值 (Take first non-None capture group)
        value = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        fields[field_name] = value
    return fields


def _format_entry(fields: dict[str, str]) -> str:
    """将字段字典格式化为一行引用字符串 (Format field dict to one-line citation string)."""
    parts: list[str] = []

    # 作者（取第一作者 last name）(Author: first author's last name)
    if author := fields.get("author", ""):
        first_author = author.split(" and ")[0].strip()
        # "Last, First" 或 "First Last" 格式 ("Last, First" or "First Last" format)
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts_name = first_author.split()
            last_name = parts_name[-1] if parts_name else first_author
        n_authors = len(author.split(" and "))
        suffix = " et al." if n_authors > 1 else ""
        parts.append(f"{last_name}{suffix}")

    # 标题 (Title)
    if title := fields.get("title", ""):
        parts.append(f'"{title}"')

    # 期刊/会议 (Journal or booktitle)
    venue = fields.get("journal") or fields.get("booktitle") or ""
    if venue:
        parts.append(venue)

    # 年份 (Year)
    if year := fields.get("year", ""):
        parts.append(year)

    return ". ".join(parts) + "." if parts else ""
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_bibtex.py -v
```

Expected: all 5 tests pass.

**Step 5: Verify quality**

```bash
uv run ruff check src/md_mid/bibtex.py tests/test_bibtex.py
uv run mypy src/md_mid/bibtex.py
```

Expected: 0 errors.

**Step 6: Commit**

```bash
git add src/md_mid/bibtex.py tests/test_bibtex.py
git commit -m "feat(bibtex): add minimal BibTeX parser for Rich Markdown footnotes"
```

---

## Task 8: CLI `-t markdown` Integration

Wire the `MarkdownRenderer` into the CLI. Add `--bib` and `--heading-id-style` options. Implement the `markdown` target branch.

**Files:**
- Modify: `src/md_mid/cli.py`
- Modify: `tests/test_cli.py` — add markdown target tests

**Step 1: Write failing tests**

```python
# Add to tests/test_cli.py

import textwrap


def test_markdown_target_basic(tmp_path) -> None:
    """基本 Markdown 转换（Basic markdown conversion works）."""
    src = tmp_path / "test.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "test.rendered.md"
    result = CliRunner().invoke(main, [str(src), "-t", "markdown", "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert "# Hello" in content
    assert "World." in content


def test_markdown_target_citation_footnote(tmp_path) -> None:
    """引用转换为脚注（Citation converted to Markdown footnote）."""
    src = tmp_path / "test.mid.md"
    src.write_text("[Wang](cite:wang2024) says hello.\n")
    out = tmp_path / "test.rendered.md"
    result = CliRunner().invoke(main, [str(src), "-t", "markdown", "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert "[^wang2024]" in content


def test_markdown_target_cross_ref(tmp_path) -> None:
    """交叉引用转换为 HTML 锚点（Cross-ref converted to HTML anchor）."""
    src = tmp_path / "test.mid.md"
    src.write_text("See [Figure 1](ref:fig:a) for details.\n")
    out = tmp_path / "test.rendered.md"
    result = CliRunner().invoke(main, [str(src), "-t", "markdown", "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert '<a href="#fig:a">Figure 1</a>' in content


def test_markdown_default_output_suffix(tmp_path) -> None:
    """Markdown 目标默认输出 .rendered.md（Default output suffix for markdown target）."""
    src = tmp_path / "test.mid.md"
    src.write_text("Hello.\n")
    result = CliRunner().invoke(main, [str(src), "-t", "markdown"])
    assert result.exit_code == 0
    assert (tmp_path / "test.rendered.md").exists()


def test_markdown_with_bib_file(tmp_path) -> None:
    """--bib 选项从 .bib 文件生成脚注（--bib option uses .bib for footnotes）."""
    src = tmp_path / "test.mid.md"
    src.write_text("[Wang](cite:wang2024) says hello.\n")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        '@article{wang2024, author={Wang, Alice}, title={Registration}, year={2024}}\n'
    )
    out = tmp_path / "out.rendered.md"
    result = CliRunner().invoke(main, [str(src), "-t", "markdown", "--bib", str(bib), "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert "Wang" in content
    assert "Registration" in content
```

**Step 2: Run to verify fails**

```bash
uv run pytest tests/test_cli.py::test_markdown_target_basic -v
```

Expected: FAIL (exit code 1, "markdown not yet implemented")

**Step 3: Update `src/md_mid/cli.py`**

Replace the `# Target not implemented` branch and add `--bib`/`--heading-id-style` options:

```python
"""md-mid CLI 入口。"""

from __future__ import annotations

import json
from pathlib import Path

import click

from md_mid import __version__
from md_mid.comment import process_comments
from md_mid.diagnostic import DiagCollector
from md_mid.latex import LaTeXRenderer
from md_mid.markdown import MarkdownRenderer
from md_mid.parser import parse


@click.command()
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.option("-t", "--target", type=click.Choice(["latex", "markdown", "html"]), default="latex")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
@click.option("--mode", type=click.Choice(["full", "body", "fragment"]), default="full")
@click.option("--strict", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.option("--dump-east", is_flag=True, default=False)
@click.option("--bib", "bib_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option(
    "--heading-id-style",
    type=click.Choice(["attr", "html"]),
    default="attr",
)
@click.version_option(version=__version__)
def main(
    input: Path,
    target: str,
    output: Path | None,
    mode: str,
    strict: bool,
    verbose: bool,
    dump_east: bool,
    bib_path: Path | None,
    heading_id_style: str,
) -> None:
    """md-mid: 学术写作中间格式转换工具"""
    text = input.read_text(encoding="utf-8")
    diag = DiagCollector(str(input))

    # 解析并处理注释指令（Parse and process comment directives）
    doc = parse(text, diag=diag)
    east = process_comments(doc, str(input), diag=diag)

    # 转储 EAST JSON 并退出（Dump EAST as JSON and exit）
    if dump_east:
        click.echo(json.dumps(east.to_dict(), ensure_ascii=False, indent=2))
        return

    if verbose:
        for d in diag.diagnostics:
            click.echo(str(d), err=True)

    if strict and diag.has_errors:
        for d in diag.errors:
            click.echo(str(d), err=True)
        raise SystemExit(1)

    if target == "latex":
        renderer = LaTeXRenderer(mode=mode, diag=diag)
        result = renderer.render(east)
        suffix = ".tex"
    elif target == "markdown":
        # 解析 .bib 文件（Parse .bib file if provided）
        bib: dict[str, str] = {}
        if bib_path is not None:
            from md_mid.bibtex import parse_bib
            bib = parse_bib(bib_path.read_text(encoding="utf-8"))
        renderer_md = MarkdownRenderer(
            bib=bib,
            heading_id_style=heading_id_style,
            diag=diag,
        )
        result = renderer_md.render(east)
        suffix = ".rendered.md"
    else:
        click.echo(f"Target '{target}' not yet implemented.", err=True)
        raise SystemExit(1)

    if output is None:
        output = input.with_suffix(suffix)

    output.write_text(result, encoding="utf-8")
    click.echo(f"Written to {output}")
```

**Step 4: Run all CLI tests**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: all tests pass (existing + 5 new).

**Step 5: Run full test suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

**Step 6: Verify quality**

```bash
uv run ruff check src/md_mid/cli.py
uv run mypy src/md_mid/cli.py
```

Expected: 0 errors.

**Step 7: Commit**

```bash
git add src/md_mid/cli.py tests/test_cli.py
git commit -m "feat(cli): add -t markdown target with --bib and --heading-id-style options"
```

---

## Task 9: Integration Tests — End-to-End Markdown Pipeline

Add an E2E test that converts the full example fixture through the markdown pipeline and validates key output patterns.

**Files:**
- Modify: `tests/test_e2e.py` — add markdown E2E test

**Step 1: Write test**

```python
# Add to tests/test_e2e.py (or create tests/test_markdown_e2e.py)

from pathlib import Path
from click.testing import CliRunner
from md_mid.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_markdown_e2e_full_example(tmp_path) -> None:
    """全示例 Markdown 转换 E2E 测试（Full example Markdown conversion E2E test）."""
    src = FIXTURES / "full_example.mid.md"
    out = tmp_path / "full.rendered.md"
    result = CliRunner().invoke(main, [str(src), "-t", "markdown", "-o", str(out)])
    assert result.exit_code == 0, result.output
    content = out.read_text()

    # 应有 YAML front matter（Should have YAML front matter）
    assert "---" in content
    assert "title:" in content

    # 交叉引用应转为 HTML 锚点（Cross-refs should be HTML anchors）
    assert "<a href=" in content

    # 引用应有脚注（Citations should have footnotes）
    assert "[^" in content

    # 图片应有 figure 块（Images should have figure blocks）
    assert "<figure" in content

    # 表格应有 HTML 表格（Tables should have HTML tables）
    assert "<table>" in content

    # 数学公式应保留（Math should be preserved）
    assert "$$" in content


def test_markdown_heading_labels_as_anchors(tmp_path) -> None:
    """标题 label 转为锚点（Heading labels become anchors）."""
    src = tmp_path / "test.mid.md"
    src.write_text("# Introduction\n<!-- label: sec:intro -->\n\nSome text.\n")
    out = tmp_path / "out.rendered.md"
    CliRunner().invoke(main, [str(src), "-t", "markdown", "-o", str(out)])
    content = out.read_text()
    assert "{#sec:intro}" in content or 'id="sec:intro"' in content
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_e2e.py -v -k markdown
```

Expected: both tests pass.

**Step 3: Run full suite**

```bash
uv run pytest --tb=short -q
uv run ruff check src/ tests/
uv run mypy src/md_mid/
```

Expected: all pass, 0 errors.

**Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test(e2e): add markdown pipeline E2E tests"
```

---

## Verification Checklist

After all tasks complete:

1. `uv run pytest --tb=short -q` → all tests pass
2. `uv run ruff check src/ tests/` → 0 errors
3. `uv run mypy src/md_mid/` → 0 errors
4. Manual: `uv run md-mid tests/fixtures/full_example.mid.md -t markdown -o /tmp/out.rendered.md && cat /tmp/out.rendered.md`
   - Should see YAML front matter, `<figure>` blocks, `[^key]` footnotes, HTML anchors
5. Manual: `uv run md-mid tests/fixtures/full_example.mid.md -t latex -o /tmp/out.tex`
   - Existing LaTeX output still works

---

## Execution Order

```
Task 1 (skeleton + basic nodes)     ─── foundation, must be first
Task 2 (cross-ref + heading labels) ─── tests only (code in Task 1)
Task 3 (citations → footnotes)      ─── tests only (code in Task 1)
Task 4 (figure rendering)           ─── tests only (code in Task 1)
Task 5 (table rendering)            ─── tests only (code in Task 1)
Task 6 (raw block + front matter)   ─── tests only (code in Task 1)
Task 7 (BibTeX parser)              ─── new module, independent
Task 8 (CLI integration)            ─── depends on Tasks 1–7
Task 9 (E2E tests)                  ─── depends on Task 8
```

Note: Tasks 2–6 are test-only tasks that validate the implementation already written in Task 1. If any test fails in Tasks 2–6, fix the implementation in `markdown.py` before proceeding.
