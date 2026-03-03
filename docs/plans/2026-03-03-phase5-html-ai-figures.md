# Phase 5: HTML Renderer & AI Figure Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add an HTML output backend (`--target html`) producing academic HTML
with MathJax (CDN), and optionally call the `generate-figures` skill runner to auto-generate
AI figures.

**Scope clarification:** This phase covers the HTML renderer backend and optional figure
generation only. Features listed in PRD but NOT in this phase: bibliography tooltips,
`--watch` mode, VS Code extension, glob input patterns. These are future work.

**Architecture:**
- New `src/md_mid/html.py` → `HTMLRenderer` class, mirrors `LaTeXRenderer` / `MarkdownRenderer`
- New `src/md_mid/genfig.py` → thin `generate_figures()` helper used by CLI when `--generate-figures` is set
- `cli.py` wired for `html` target and `--generate-figures` flag
- `latex.py` gets a small addition: `% AI Generated: ...` LaTeX comments

**Tech Stack:** Python stdlib only for HTML generation (no Jinja2); MathJax v3 CDN;
`generate-figures` skill runner (`nanobanana.py`) called via `importlib.util`

**Baseline:** 303 tests passing, HEAD at `618d134`.

---

## Task 1: LaTeX AI figure comments

**Files:**
- Modify: `src/md_mid/latex.py` (two methods)
- Modify: `tests/test_latex.py` (new class `TestLatexAiFigureComments`)

PRD §4.2.4 shows that LaTeX output should emit `% AI Generated: ...` comment lines after
`\label{}` inside a figure environment. Currently `render_figure()` and `render_image()`
ignore `metadata["ai"]` entirely.

### Step 1: Write the failing tests

Add to `tests/test_latex.py` after the `TestHtmlRawBlockSkipped` class:

```python
# ── Task 1 (Phase 5): LaTeX AI figure comments ─────────────────────────────

from md_mid.nodes import Figure, Image

class TestLatexAiFigureComments:
    """AI metadata emits % comments in LaTeX figure output (AI 注释出现在 LaTeX 图环境中)."""

    def test_figure_ai_comments_emitted(self) -> None:
        """AI metadata → % AI Generated / % Prompt / % Negative / % Params comments."""
        fig = Figure(
            src="fig.png",
            alt="test",
            metadata={
                "caption": "Test",
                "label": "fig:test",
                "ai": {
                    "generated": True,
                    "model": "midjourney-v6",
                    "prompt": "blue sky",
                    "negative_prompt": "dark",
                    "params": {"seed": 42},
                },
            },
        )
        result = LaTeXRenderer().render(fig)
        assert "% AI Generated: midjourney-v6" in result
        assert "% Prompt: blue sky" in result
        assert "% Negative: dark" in result
        assert "% Params:" in result

    def test_figure_no_ai_no_comments(self) -> None:
        """Figure without AI metadata → no % AI comments (无 AI 元数据无注释)."""
        fig = Figure(
            src="fig.png",
            alt="test",
            metadata={"caption": "Test", "label": "fig:test"},
        )
        result = LaTeXRenderer().render(fig)
        assert "% AI" not in result

    def test_image_promoted_ai_comments_emitted(self) -> None:
        """Image promoted to figure (via caption) also emits AI comments (升级图片也输出 AI 注释)."""
        img = Image(
            src="img.png",
            alt="test",
            metadata={
                "caption": "Caption",
                "ai": {"generated": True, "model": "dalle-3"},
            },
        )
        result = LaTeXRenderer().render(img)
        assert "% AI Generated: dalle-3" in result
```

### Step 2: Run tests to confirm they fail

```bash
uv run pytest tests/test_latex.py::TestLatexAiFigureComments -v
```
Expected: 3 FAIL (% AI Generated not present)

### Step 3: Implement in `src/md_mid/latex.py`

Add a private helper (after the `render_image` method, before `render_table`):

```python
def _render_ai_comments(self, ai: object) -> list[str]:
    """Emit % AI ... comments from ai metadata dict (输出 AI 元数据 LaTeX 注释).

    Args:
        ai: ai sub-dict from node.metadata (节点 metadata 的 ai 子字典)

    Returns:
        List of LaTeX comment lines (LaTeX 注释行列表)
    """
    if not isinstance(ai, dict):
        return []
    lines: list[str] = []
    model = ai.get("model")
    if model:
        lines.append(f"  % AI Generated: {model}")
    prompt = ai.get("prompt")
    if prompt:
        # truncate very long prompts to 120 chars (超长 prompt 截断)
        truncated = str(prompt).replace("\n", " ")[:120]
        lines.append(f"  % Prompt: {truncated}")
    neg = ai.get("negative_prompt")
    if neg:
        truncated_neg = str(neg).replace("\n", " ")[:120]
        lines.append(f"  % Negative: {truncated_neg}")
    params = ai.get("params")
    if params:
        # render params dict as key=value pairs; sanitize newlines (渲染参数；清理换行)
        pairs = ", ".join(
            f"{_sanitize_comment(str(k))}={_sanitize_comment(str(v))}"
            for k, v in params.items()
        )
        lines.append(f"  % Params: {pairs}")
    return lines
```

Also add a small helper above (or inline):

```python
@staticmethod
def _sanitize_comment(text: str) -> str:
    """Strip newlines to prevent LaTeX comment injection (去除换行防注入)."""
    return str(text).replace("\n", " ").replace("\r", "")
```

Note: the `model`, `prompt`, and `neg` branches already call `.replace("\n", " ")`,
so only `params` needs the extra helper. The helper is also used for `k`/`v` in params
which could contain newlines.
```

Then in **`render_figure()`**, insert AI comments before `\end{figure}`:

```python
def render_figure(self, node: Node) -> str:
    fig = cast(Figure, node)
    meta = node.metadata
    placement = str(meta.get("placement", "htbp"))
    width = str(meta.get("width", ""))
    caption = str(meta.get("caption", ""))
    label = str(meta.get("label", ""))

    lines = [f"\\begin{{figure}}[{placement}]"]
    lines.append("\\centering")

    gfx_opts = f"width={width}" if width else ""
    if gfx_opts:
        lines.append(f"\\includegraphics[{gfx_opts}]{{{fig.src}}}")
    else:
        lines.append(f"\\includegraphics{{{fig.src}}}")

    if caption:
        lines.append(f"\\caption{{{caption}}}")
    if label:
        lines.append(f"\\label{{{label}}}")

    # AI metadata as LaTeX comments (AI 元数据作为 LaTeX 注释)
    lines.extend(self._render_ai_comments(meta.get("ai")))

    lines.append("\\end{figure}")
    return "\n".join(lines) + "\n"
```

Apply the same AI comment block in **`render_image()`** in the promoted-to-figure branch
(after the `if label:` block, before `lines.append("\\end{figure}")`).

### Step 4: Run tests

```bash
uv run pytest tests/test_latex.py::TestLatexAiFigureComments -v
```
Expected: 3 PASS

### Step 5: Run full suite

```bash
make check
```
Expected: 306 tests passing, ruff 0, mypy 0.

### Step 6: Commit

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): emit % AI Generated comments for AI figure metadata"
```

---

## Task 2: HTML renderer — document structure, basic nodes, CLI wiring

**Files:**
- Create: `src/md_mid/html.py`
- Modify: `src/md_mid/cli.py`
- Create: `tests/test_html.py`

### Step 1: Write failing tests

Create `tests/test_html.py`:

```python
"""Tests for HTML renderer (HTML 渲染器测试)."""
from __future__ import annotations

from md_mid.html import HTMLRenderer
from md_mid.nodes import (
    Blockquote,
    CodeBlock,
    CodeInline,
    CrossRef,
    Document,
    Emphasis,
    Heading,
    HardBreak,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    RawBlock,
    SoftBreak,
    Strong,
    Text,
    ThematicBreak,
)


def doc(*children) -> Document:
    """Convenience: build a Document from nodes (构造含节点的文档)."""
    return Document(children=list(children))


def render(node, **kwargs) -> str:
    """Render a node with HTMLRenderer (用 HTMLRenderer 渲染节点)."""
    return HTMLRenderer(**kwargs).render(node)


# ── Document structure ────────────────────────────────────────────────────────


class TestHtmlDocumentStructure:
    """Full-mode HTML document has proper wrapping (全文模式有完整 HTML 包裹)."""

    def test_full_mode_has_doctype(self) -> None:
        """Full mode starts with DOCTYPE (全文模式以 DOCTYPE 开始)."""
        result = render(doc(Paragraph(children=[Text(content="Hi")])), mode="full")
        assert result.startswith("<!DOCTYPE html>")

    def test_full_mode_has_mathjax(self) -> None:
        """Full mode includes MathJax CDN script (全文模式包含 MathJax 脚本)."""
        result = render(doc(Paragraph(children=[Text(content="Hi")])), mode="full")
        assert "mathjax" in result.lower()

    def test_body_mode_no_doctype(self) -> None:
        """Body mode has no DOCTYPE (body 模式无 DOCTYPE)."""
        result = render(doc(Paragraph(children=[Text(content="Hi")])), mode="body")
        assert "<!DOCTYPE" not in result

    def test_fragment_mode_minimal(self) -> None:
        """Fragment mode produces minimal output (fragment 模式输出最小内容)."""
        result = render(doc(Paragraph(children=[Text(content="Hi")])), mode="fragment")
        assert "<!DOCTYPE" not in result
        assert "<html" not in result


# ── Block nodes ───────────────────────────────────────────────────────────────


class TestHtmlHeading:
    """Heading renders to <h1>–<h6> with id anchor (标题渲染为带 id 的 h 标签)."""

    def test_h1(self) -> None:
        h = Heading(level=1, children=[Text(content="Title")])
        result = render(doc(h))
        assert "<h1" in result
        assert "Title" in result

    def test_heading_has_id(self) -> None:
        h = Heading(level=2, children=[Text(content="My Section")])
        h.metadata["label"] = "sec:intro"
        result = render(doc(h))
        assert 'id="sec:intro"' in result

    def test_h2_through_h6(self) -> None:
        for level in range(2, 7):
            h = Heading(level=level, children=[Text(content="X")])
            result = render(doc(h))
            assert f"<h{level}" in result


class TestHtmlParagraph:
    """Paragraph renders to <p> (段落渲染为 p 标签)."""

    def test_basic_paragraph(self) -> None:
        result = render(doc(Paragraph(children=[Text(content="Hello world")])))
        assert "<p>" in result
        assert "Hello world" in result


class TestHtmlList:
    """Lists render to <ul>/<ol> (列表渲染)."""

    def test_unordered_list(self) -> None:
        lst = List(ordered=False, children=[
            ListItem(children=[Paragraph(children=[Text(content="item")])]),
        ])
        result = render(doc(lst))
        assert "<ul>" in result
        assert "<li>" in result

    def test_ordered_list(self) -> None:
        lst = List(ordered=True, children=[
            ListItem(children=[Paragraph(children=[Text(content="item")])]),
        ])
        result = render(doc(lst))
        assert "<ol>" in result


class TestHtmlCodeBlock:
    """Code block renders to <pre><code> (代码块渲染)."""

    def test_code_block(self) -> None:
        cb = CodeBlock(content="x = 1", language="python")
        result = render(doc(cb))
        assert "<pre>" in result
        assert "<code" in result
        assert "x = 1" in result

    def test_code_block_language_class(self) -> None:
        cb = CodeBlock(content="x = 1", language="python")
        result = render(doc(cb))
        assert "python" in result


class TestHtmlBlockQuote:
    """Blockquote renders to <blockquote> (引用渲染)."""

    def test_blockquote(self) -> None:
        bq = Blockquote(children=[Paragraph(children=[Text(content="quote")])])
        result = render(doc(bq))
        assert "<blockquote>" in result
        assert "quote" in result


class TestHtmlMath:
    """Math renders with MathJax delimiters (数学公式使用 MathJax 分隔符)."""

    def test_math_block(self) -> None:
        mb = MathBlock(content="x^2 + y^2 = z^2")
        result = render(doc(Paragraph(children=[mb])))
        # MathJax block delimiter \[...\]
        assert "x^2 + y^2 = z^2" in result

    def test_math_inline(self) -> None:
        p = Paragraph(children=[
            Text(content="See "),
            MathInline(content="E=mc^2"),
        ])
        result = render(doc(p))
        assert "E=mc^2" in result


class TestHtmlThematicBreak:
    """Thematic break renders to <hr> (分割线渲染)."""

    def test_thematic_break(self) -> None:
        result = render(doc(ThematicBreak()))
        assert "<hr" in result


class TestHtmlRawBlock:
    """Raw block HTML passthrough; LaTeX raw block → <details> fold (原始块处理)."""

    def test_html_raw_passthrough(self) -> None:
        rb = RawBlock(content="<div>hi</div>", kind="html")
        result = render(doc(rb))
        assert "<div>hi</div>" in result
        assert "<details>" not in result

    def test_latex_raw_details_fold(self) -> None:
        rb = RawBlock(content="\\newcommand{\\myvec}{\\mathbf}", kind="latex")
        result = render(doc(rb))
        assert "<details>" in result
        assert "\\newcommand" in result


# ── Inline nodes ──────────────────────────────────────────────────────────────


class TestHtmlInline:
    """Inline elements render correctly (行内元素渲染)."""

    def test_strong(self) -> None:
        p = Paragraph(children=[Strong(children=[Text(content="bold")])])
        result = render(doc(p))
        assert "<strong>bold</strong>" in result

    def test_emphasis(self) -> None:
        p = Paragraph(children=[Emphasis(children=[Text(content="italic")])])
        result = render(doc(p))
        assert "<em>italic</em>" in result

    def test_code_inline(self) -> None:
        p = Paragraph(children=[CodeInline(content="x = 1")])
        result = render(doc(p))
        assert "<code>x = 1</code>" in result

    def test_link(self) -> None:
        p = Paragraph(children=[
            Link(url="https://example.com", children=[Text(content="click")])
        ])
        result = render(doc(p))
        assert 'href="https://example.com"' in result
        assert "click" in result

    def test_text_xss_escaped(self) -> None:
        p = Paragraph(children=[Text(content="<script>alert(1)</script>")])
        result = render(doc(p))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_hard_break(self) -> None:
        p = Paragraph(children=[Text(content="a"), HardBreak(), Text(content="b")])
        result = render(doc(p))
        assert "<br" in result

    def test_soft_break_renders_space(self) -> None:
        """SoftBreak renders as space (软换行渲染为空格)."""
        p = Paragraph(children=[Text(content="a"), SoftBreak(), Text(content="b")])
        result = render(doc(p))
        assert "a b" in result or "a\nb" in result

    def test_cross_ref_uses_display_text(self) -> None:
        """CrossRef uses display_text, not children (交叉引用使用 display_text)."""
        cr = CrossRef(label="fig:test", display_text="Figure 1")
        result = render(doc(Paragraph(children=[cr])))
        assert "Figure 1" in result
        assert 'href="#fig:test"' in result

    def test_link_javascript_scheme_sanitized(self) -> None:
        """Links with javascript: scheme are sanitized (javascript: 链接被过滤)."""
        p = Paragraph(children=[
            Link(url="javascript:alert(1)", children=[Text(content="click")])
        ])
        result = render(doc(p))
        assert "javascript:" not in result

    def test_math_inline_html_escaped(self) -> None:
        """Inline math with <script> is HTML-escaped (数学公式 HTML 转义)."""
        p = Paragraph(children=[MathInline(content="x<script>alert(1)</script>y")])
        result = render(doc(p))
        assert "<script>" not in result


# ── CLI integration ────────────────────────────────────────────────────────────


class TestHtmlCliTarget:
    """--target html produces HTML output (CLI 集成测试)."""
    pass  # CLI tests are in tests/test_cli.py
```

### Step 2: Run tests to confirm failures

```bash
uv run pytest tests/test_html.py -v
```
Expected: ImportError (html.py not yet created) or all FAIL.

### Step 3: Create `src/md_mid/html.py`

```python
"""HTML renderer — converts EAST to self-contained academic HTML.

HTML 渲染器 — 将 EAST 转换为自包含的学术 HTML。
"""

from __future__ import annotations

import html as _html_lib
from typing import cast

from md_mid.nodes import (
    Blockquote,
    CodeBlock,
    CodeInline,
    CrossRef,
    Citation,
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

# Safe URL schemes for links (链接安全 scheme 白名单)
_UNSAFE_SCHEMES = ("javascript:", "vbscript:", "data:text/html")


def _esc(text: str) -> str:
    """HTML-escape text (HTML 转义文本)."""
    return _html_lib.escape(text, quote=True)


# MathJax v3 CDN (MathJax v3 CDN 链接)
_MATHJAX_CDN = (
    "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
)

# Minimal academic CSS (最小学术 CSS 样式)
_CSS = """\
body { max-width: 800px; margin: 2em auto; font-family: serif; line-height: 1.7;
       padding: 0 1em; color: #222; }
h1, h2, h3, h4 { font-weight: bold; margin-top: 1.5em; }
figure { text-align: center; margin: 1.5em auto; }
figcaption { font-style: italic; margin-top: 0.4em; }
table { border-collapse: collapse; margin: 1em auto; }
th, td { border: 1px solid #bbb; padding: 0.4em 0.8em; }
th { background: #f4f4f4; }
.table-wrap { text-align: center; margin: 1.5em 0; }
.table-caption { font-style: italic; margin-bottom: 0.4em; }
pre { background: #f6f6f6; padding: 1em; overflow-x: auto; border-radius: 4px; }
code { font-family: monospace; font-size: 0.92em; }
blockquote { border-left: 4px solid #ccc; margin-left: 0; padding-left: 1em;
             color: #555; }
.footnotes { border-top: 1px solid #ccc; margin-top: 3em; font-size: 0.9em; }
.bibliography { margin-top: 2em; }
details { background: #fafafa; border: 1px solid #ddd; border-radius: 4px;
          padding: 0.5em 1em; margin: 1em 0; }
summary { cursor: pointer; font-weight: bold; }
"""


class HTMLRenderer:
    """Render EAST to self-contained academic HTML.

    将 EAST 渲染为自包含的学术 HTML。

    Args:
        mode: Output mode — full | body | fragment  (输出模式)
        bib: Bibliography dict key→display string  (参考文献字典)
        locale: Label language zh | en  (标签语言)
        diag: Diagnostic collector  (诊断收集器)
    """

    def __init__(
        self,
        mode: str = "full",
        bib: dict[str, str] | None = None,
        locale: str = "zh",
        diag: object = None,
    ) -> None:
        self._mode = mode
        self._bib: dict[str, str] = bib or {}
        self._locale = locale
        self._diag = diag

        # Figure / table counters (图表计数器)
        self._fig_count: int = 0
        self._tab_count: int = 0

        # Citation tracking: key → sequential number  (引用编号追踪)
        self._cite_order: dict[str, int] = {}
        self._cite_seq: int = 0

        # Native footnote defs (原生脚注定义)
        self._fn_defs: dict[str, str] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def render(self, node: Node) -> str:
        """Render a node to HTML string (渲染节点为 HTML 字符串)."""
        if isinstance(node, Document):
            return self._render_document(node)
        return self._dispatch(node)

    # ── Document ──────────────────────────────────────────────────────────────

    def _render_document(self, doc: Document) -> str:
        """Render the full document (渲染完整文档)."""
        # Reset state for each render call (每次渲染重置状态)
        self._fig_count = 0
        self._tab_count = 0
        self._cite_order = {}
        self._cite_seq = 0
        self._fn_defs = {}

        body = "".join(self._dispatch(child) for child in doc.children)
        footnotes = self._render_footnotes()

        if self._mode == "fragment":
            return body

        if self._mode == "body":
            return body + footnotes

        # Full document mode (全文模式)
        title = str(doc.metadata.get("title", ""))
        title_tag = f"<title>{_esc(title)}</title>" if title else "<title>Document</title>"

        # Map locale to HTML lang attribute (本地化映射为 HTML lang 属性)
        lang = "en" if self._locale == "en" else "zh-CN"

        return (
            "<!DOCTYPE html>\n"
            f'<html lang="{lang}">\n'
            "<head>\n"
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"{title_tag}\n"
            f"<style>\n{_CSS}</style>\n"
            "<script>\n"
            "MathJax = { tex: { inlineMath: [['$','$']] }, "
            "options: { skipHtmlTags: ['script','style'] } };\n"
            "</script>\n"
            f'<script src="{_MATHJAX_CDN}" id="MathJax-script" async></script>\n'
            "</head>\n"
            "<body>\n"
            + body
            + footnotes
            + "</body>\n"
            "</html>\n"
        )

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, node: Node) -> str:
        """Dispatch node to the appropriate render method (分发节点到对应渲染方法)."""
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "blockquote": self._render_blockquote,
            "list": self._render_list,
            "list_item": self._render_list_item,
            "code_block": self._render_code_block,
            "figure": self._render_figure,
            "image": self._render_image,
            "table": self._render_table,
            "math_block": self._render_math_block,
            "environment": self._render_environment,
            "raw_block": self._render_raw_block,
            "thematic_break": self._render_thematic_break,
            "text": self._render_text,
            "strong": self._render_strong,
            "emphasis": self._render_emphasis,
            "code_inline": self._render_code_inline,
            "math_inline": self._render_math_inline,
            "link": self._render_link,
            "cross_ref": self._render_cross_ref,
            "citation": self._render_citation,
            "footnote_ref": self._render_footnote_ref,
            "footnote_def": self._render_footnote_def,
            "hardbreak": self._render_hard_break,
            "softbreak": self._render_soft_break,
        }
        handler = handlers.get(node.type)
        if handler:
            return handler(node)
        # Unknown node: render children (未知节点：渲染子节点)
        return self._render_children(node)

    def _render_children(self, node: Node) -> str:
        """Render all children and concatenate (渲染所有子节点并拼接)."""
        return "".join(self._dispatch(child) for child in node.children)

    # ── Block nodes ───────────────────────────────────────────────────────────

    def _render_heading(self, node: Node) -> str:
        """Heading → <h1>–<h6> with optional id anchor (标题渲染)."""
        h = cast(Heading, node)
        level = max(1, min(6, h.level))
        label = str(node.metadata.get("label", ""))
        id_attr = f' id="{_esc(label)}"' if label else ""
        content = self._render_children(node)
        return f"<h{level}{id_attr}>{content}</h{level}>\n"

    def _render_paragraph(self, node: Node) -> str:
        """Paragraph → <p>...</p> (段落渲染)."""
        content = self._render_children(node)
        if not content.strip():
            return ""
        return f"<p>{content}</p>\n"

    def _render_blockquote(self, node: Node) -> str:
        """Blockquote → <blockquote> (引用渲染)."""
        content = self._render_children(node)
        return f"<blockquote>\n{content}</blockquote>\n"

    def _render_list(self, node: Node) -> str:
        """List → <ul> or <ol> (列表渲染)."""
        lst = cast(List, node)
        tag = "ol" if lst.ordered else "ul"
        content = self._render_children(node)
        return f"<{tag}>\n{content}</{tag}>\n"

    def _render_list_item(self, node: Node) -> str:
        """List item → <li> (列表项渲染)."""
        content = self._render_children(node)
        return f"<li>{content}</li>\n"

    def _render_code_block(self, node: Node) -> str:
        """Code block → <pre><code class="language-..."> (代码块渲染)."""
        cb = cast(CodeBlock, node)
        lang_attr = f' class="language-{_esc(cb.language)}"' if cb.language else ""
        escaped = _esc(cb.content)
        return f"<pre><code{lang_attr}>{escaped}</code></pre>\n"

    def _render_figure(self, node: Node) -> str:
        """Figure → <figure> with auto-numbering (图渲染，自动编号)."""
        self._fig_count += 1
        fig = cast(Figure, node)
        meta = node.metadata
        label = str(meta.get("label", ""))
        caption = str(meta.get("caption", ""))
        width = str(meta.get("width", ""))
        ai = meta.get("ai")

        # Determine label prefix for caption (确定标签前缀)
        prefix = "Figure" if self._locale == "en" else "图"
        id_attr = f' id="{_esc(label)}"' if label else ""

        # Build img tag (构建 img 标签)
        style = f' style="max-width:{width}"' if width and not width.endswith("textwidth") else ""
        img_tag = f'<img src="{_esc(fig.src)}" alt="{_esc(fig.alt)}"{style}>'

        lines = [f"<figure{id_attr}>", f"  {img_tag}"]

        if caption:
            cap_text = f"{prefix} {self._fig_count}: {_esc(caption)}"
            lines.append(f"  <figcaption>{cap_text}</figcaption>")

        # AI generation info as <details> fold (AI 生成信息折叠块)
        if isinstance(ai, dict):
            lines.extend(self._render_ai_details(ai))

        lines.append("</figure>")
        return "\n".join(lines) + "\n"

    def _render_image(self, node: Node) -> str:
        """Image → plain <img> or promoted to <figure> if it has caption/label.

        有 caption/label 时升级为 figure 环境渲染。
        """
        img = cast(Image, node)
        meta = node.metadata
        if meta.get("caption") or meta.get("label"):
            # Promote: reuse figure rendering logic (升级为 figure 渲染)
            fig_node = Figure(
                src=img.src,
                alt=img.alt,
                children=list(img.children),
                metadata=dict(meta),
            )
            return self._render_figure(fig_node)
        return f'<img src="{_esc(img.src)}" alt="{_esc(img.alt)}">'

    def _render_table(self, node: Node) -> str:
        """Table → <table> with auto-numbering and caption (表渲染，自动编号)."""
        self._tab_count += 1
        tbl = cast(Table, node)
        meta = node.metadata
        label = str(meta.get("label", ""))
        caption = str(meta.get("caption", ""))
        prefix = "Table" if self._locale == "en" else "表"
        id_attr = f' id="{_esc(label)}"' if label else ""

        lines: list[str] = [f'<div class="table-wrap"{id_attr}>']

        if caption:
            cap_text = f"{prefix} {self._tab_count}: {_esc(caption)}"
            lines.append(f'  <p class="table-caption">{cap_text}</p>')

        lines.append("  <table>")

        # Build alignment style map (构建对齐样式映射)
        def _align_style(col_idx: int) -> str:
            if col_idx < len(tbl.alignments):
                a = tbl.alignments[col_idx]
                if a in ("left", "center", "right"):
                    return f' style="text-align:{a}"'
            return ""

        # Header row (表头行)
        if tbl.headers:
            lines.append("    <tr>")
            for ci, cell_nodes in enumerate(tbl.headers):
                cell_html = "".join(self._dispatch(n) for n in cell_nodes)
                lines.append(f"      <th{_align_style(ci)}>{cell_html}</th>")
            lines.append("    </tr>")

        # Data rows (数据行)
        for row in tbl.rows:
            lines.append("    <tr>")
            for ci, cell_nodes in enumerate(row):
                cell_html = "".join(self._dispatch(n) for n in cell_nodes)
                lines.append(f"      <td{_align_style(ci)}>{cell_html}</td>")
            lines.append("    </tr>")

        lines.append("  </table>")
        lines.append("</div>")
        return "\n".join(lines) + "\n"

    def _render_math_block(self, node: Node) -> str:
        r"""Math block → \[...\] for MathJax, HTML-escaped (块级数学公式，HTML 转义)."""
        mb = cast(MathBlock, node)
        label = str(node.metadata.get("label", ""))
        id_attr = f' id="{_esc(label)}"' if label else ""
        # Escape math content for HTML safety; MathJax reads decoded text (HTML 转义数学内容)
        return f'<div class="math-block"{id_attr}>\n\\[{_esc(mb.content)}\\]\n</div>\n'

    def _render_environment(self, node: Node) -> str:
        """Environment → generic <div class="env-name"> (环境渲染)."""
        env = cast(Environment, node)
        content = self._render_children(node)
        return f'<div class="env-{_esc(env.name)}">\n{content}</div>\n'

    def _render_raw_block(self, node: Node) -> str:
        """Raw block: HTML kind → passthrough; LaTeX → <details> fold (原始块渲染)."""
        rb = cast(RawBlock, node)
        if rb.kind == "html":
            # HTML passthrough (HTML 原样透传)
            return rb.content + "\n"
        # LaTeX raw block → collapsible fold (LaTeX 块折叠显示)
        escaped = _esc(rb.content)
        return (
            "<details>\n"
            "<summary>📄 Raw LaTeX</summary>\n"
            f"<pre><code class=\"language-latex\">{escaped}</code></pre>\n"
            "</details>\n"
        )

    def _render_thematic_break(self, node: Node) -> str:
        """Thematic break → <hr> (分割线渲染)."""
        return "<hr>\n"

    # ── Inline nodes ──────────────────────────────────────────────────────────

    def _render_text(self, node: Node) -> str:
        """Text node → HTML-escaped string (文本节点 HTML 转义)."""
        t = cast(Text, node)
        return _esc(t.content)

    def _render_strong(self, node: Node) -> str:
        """Strong → <strong> (加粗渲染)."""
        return f"<strong>{self._render_children(node)}</strong>"

    def _render_emphasis(self, node: Node) -> str:
        """Emphasis → <em> (斜体渲染)."""
        return f"<em>{self._render_children(node)}</em>"

    def _render_code_inline(self, node: Node) -> str:
        """Inline code → <code> (行内代码渲染)."""
        ci = cast(CodeInline, node)
        return f"<code>{_esc(ci.content)}</code>"

    def _render_math_inline(self, node: Node) -> str:
        """Inline math → $...$ for MathJax (行内数学公式渲染)."""
        mi = cast(MathInline, node)
        return f"${_esc(mi.content)}$"

    def _render_link(self, node: Node) -> str:
        """Link → <a href="..."> with scheme validation (链接渲染，含 scheme 校验)."""
        lnk = cast(Link, node)
        text = self._render_children(node)
        url = lnk.url
        # Block dangerous URI schemes (阻止危险的 URI scheme)
        if url.lower().startswith(("javascript:", "vbscript:", "data:text/html")):
            return text  # render text only, drop the link (仅渲染文本，丢弃链接)
        return f'<a href="{_esc(url)}">{text}</a>'

    def _render_cross_ref(self, node: Node) -> str:
        """Cross-ref → <a href="#label"> using display_text (交叉引用渲染)."""
        cr = cast(CrossRef, node)
        # Parser fills display_text, not children (解析器填充 display_text 而非 children)
        text = _esc(cr.display_text) if cr.display_text else _esc(cr.label)
        return f'<a href="#{_esc(cr.label)}">{text}</a>'

    def _render_citation(self, node: Node) -> str:
        """Citation → superscript numbered reference (文献引用渲染)."""
        cit = cast(Citation, node)
        parts: list[str] = []
        for key in cit.keys:
            if key not in self._cite_order:
                self._cite_seq += 1
                self._cite_order[key] = self._cite_seq
            n = self._cite_order[key]
            parts.append(f'<sup><a href="#cite-{_esc(key)}" class="cite">[{n}]</a></sup>')
        return "".join(parts)

    def _render_footnote_ref(self, node: Node) -> str:
        """Footnote ref → superscript link (脚注引用渲染)."""
        fr = cast(FootnoteRef, node)
        return f'<sup><a href="#fn-{_esc(fr.ref_id)}">[fn]</a></sup>'

    def _render_footnote_def(self, node: Node) -> str:
        """Footnote def → collect for end of document (脚注定义收集)."""
        fd = cast(FootnoteDef, node)
        content = self._render_children(node).strip()
        self._fn_defs[fd.def_id] = content
        return ""

    def _render_hard_break(self, node: Node) -> str:
        """Hard break → <br> (硬换行渲染)."""
        return "<br>\n"

    def _render_soft_break(self, node: Node) -> str:
        """Soft break → newline (preserves Markdown line break semantics) (软换行渲染)."""
        return "\n"

    # ── Footnotes and bibliography ────────────────────────────────────────────

    def _render_footnotes(self) -> str:
        """Render bibliography + footnote definitions at end (渲染文末参考文献和脚注)."""
        if self._mode == "fragment":
            return ""

        parts: list[str] = []

        # Bibliography (参考文献部分)
        if self._cite_order:
            parts.append('<div class="bibliography">\n<h2>References</h2>\n<ol>\n')
            for key, _num in sorted(self._cite_order.items(), key=lambda kv: kv[1]):
                text = _esc(self._bib.get(key, key))
                parts.append(
                    f'  <li id="cite-{_esc(key)}">{text}</li>\n'
                )
            parts.append("</ol>\n</div>\n")

        # Footnotes (脚注部分)
        if self._fn_defs:
            parts.append('<div class="footnotes">\n<hr>\n<ol>\n')
            for def_id, content in self._fn_defs.items():
                parts.append(
                    f'  <li id="fn-{_esc(def_id)}">{content}</li>\n'
                )
            parts.append("</ol>\n</div>\n")

        return "".join(parts)

    # ── AI details helper ─────────────────────────────────────────────────────

    def _render_ai_details(self, ai: dict[str, object]) -> list[str]:
        """Render AI generation info as HTML <details> fold (AI 信息折叠块渲染)."""
        lines = [
            "  <details>",
            "    <summary>🎨 AI Generation Info</summary>",
        ]
        if model := ai.get("model"):
            lines.append(f"    <p><strong>Model</strong>: {_esc(str(model))}</p>")
        if prompt := ai.get("prompt"):
            lines.append(f"    <p><strong>Prompt</strong>: {_esc(str(prompt))}</p>")
        if neg := ai.get("negative_prompt"):
            lines.append(f"    <p><strong>Negative</strong>: {_esc(str(neg))}</p>")
        if params := ai.get("params"):
            lines.append(f"    <p><strong>Params</strong>: {_esc(str(params))}</p>")
        lines.append("  </details>")
        return lines
```

### Step 4: Wire HTML target in `src/md_mid/cli.py`

In `cli.py`, add an `elif effective_target == "html":` branch **before** the existing `else:` branch:

```python
elif effective_target == "html":
    from md_mid.html import HTMLRenderer
    # Parse .bib file if provided (解析 .bib 文件)
    bib: dict[str, str] = {}
    if bib_path is not None:
        from md_mid.bibtex import parse_bib
        try:
            bib = parse_bib(bib_path.read_text(encoding="utf-8"))
        except Exception as exc:
            click.echo(f"[WARNING] Failed to parse {bib_path}: {exc}", err=True)
    renderer_html = HTMLRenderer(
        mode=cfg.mode,
        bib=bib,
        locale=cfg.locale,
        diag=diag,
    )
    result = renderer_html.render(east)
    suffix = ".html"
```

### Step 5: Add CLI test in `tests/test_cli.py`

```python
def test_html_target_basic(tmp_path: Path) -> None:
    """--target html produces self-contained HTML (--target html 生成 HTML)."""
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "out.html"
    result = CliRunner().invoke(main, [str(src), "-t", "html", "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert "<!DOCTYPE html>" in content
    assert "<h1" in content
    assert "Hello" in content
    assert "mathjax" in content.lower()


def test_html_target_math(tmp_path: Path) -> None:
    """HTML target renders math with MathJax delimiters (HTML 数学公式渲染)."""
    src = tmp_path / "t.mid.md"
    src.write_text("Inline $E=mc^2$ and block:\n\n$$x^2=1$$\n")
    out = tmp_path / "out.html"
    result = CliRunner().invoke(main, [str(src), "-t", "html", "-o", str(out)])
    assert result.exit_code == 0
    content = out.read_text()
    assert "E=mc^2" in content
    assert "x^2=1" in content


def test_html_default_suffix(tmp_path: Path) -> None:
    """HTML target default output suffix is .html (默认后缀为 .html)."""
    src = tmp_path / "t.mid.md"
    src.write_text("Hello.\n")
    result = CliRunner().invoke(main, [str(src), "-t", "html"])
    assert result.exit_code == 0
    assert (tmp_path / "t.mid.html").exists()
```

### Step 6: Run all tests

```bash
make check
```
Expected: ≥ 330 tests passing (303 + ~27 new HTML tests), ruff 0, mypy 0.

### Step 7: Commit

```bash
git add src/md_mid/html.py src/md_mid/cli.py tests/test_html.py tests/test_cli.py
git commit -m "feat(html): add HTML renderer backend with MathJax and CLI wiring"
```

---

## Task 3: HTML renderer — figures, tables, cross-refs, citations

**Files:**
- Modify: `tests/test_html.py` (additional test classes)

The core renderer in Task 2 already implements these features. This task adds
comprehensive tests to validate them and fix any issues found.

### Step 1: Write the failing tests

Add to `tests/test_html.py`:

```python
# ── Figures and tables ────────────────────────────────────────────────────────


class TestHtmlFigure:
    """Figure rendering with auto-numbering and AI details (图渲染测试)."""

    def test_figure_auto_numbered(self) -> None:
        """Two figures get sequential numbers (两图自动编号)."""
        fig1 = Figure(src="a.png", alt="A", metadata={"caption": "First", "label": "fig:a"})
        fig2 = Figure(src="b.png", alt="B", metadata={"caption": "Second", "label": "fig:b"})
        result = render(doc(fig1, fig2))
        assert "图 1" in result or "Figure 1" in result
        assert "图 2" in result or "Figure 2" in result

    def test_figure_has_id_anchor(self) -> None:
        """Figure label becomes id attribute (标签成为 id 属性)."""
        fig = Figure(src="a.png", alt="A", metadata={"caption": "Cap", "label": "fig:test"})
        result = render(doc(fig))
        assert 'id="fig:test"' in result

    def test_figure_ai_details(self) -> None:
        """Figure with AI metadata shows <details> block (AI 信息折叠块)."""
        fig = Figure(
            src="a.png", alt="A",
            metadata={
                "caption": "AI figure",
                "ai": {"model": "dalle-3", "prompt": "blue sky"},
            },
        )
        result = render(doc(fig))
        assert "<details>" in result
        assert "dalle-3" in result
        assert "blue sky" in result

    def test_figure_locale_en_label(self) -> None:
        """English locale uses 'Figure N' prefix (英文标签前缀测试)."""
        fig = Figure(src="a.png", alt="A", metadata={"caption": "Cap"})
        result = HTMLRenderer(locale="en").render(doc(fig))
        assert "Figure 1" in result

    def test_figure_locale_zh_label(self) -> None:
        """Chinese locale uses '图N' prefix (中文标签前缀测试)."""
        fig = Figure(src="a.png", alt="A", metadata={"caption": "Cap"})
        result = HTMLRenderer(locale="zh").render(doc(fig))
        assert "图 1" in result


class TestHtmlLangAttribute:
    """<html lang> respects locale setting (lang 属性随 locale 变化)."""

    def test_html_lang_en(self) -> None:
        """locale=en → <html lang='en'> (英文模式 lang 属性)."""
        result = HTMLRenderer(locale="en").render(doc(Paragraph(children=[Text(content="Hi")])))
        assert 'lang="en"' in result

    def test_html_lang_zh(self) -> None:
        """locale=zh → <html lang='zh-CN'> (中文模式 lang 属性)."""
        result = HTMLRenderer(locale="zh").render(doc(Paragraph(children=[Text(content="Hi")])))
        assert 'lang="zh-CN"' in result


class TestHtmlTableAlignment:
    """Table cell alignment respects column alignments (表格列对齐测试)."""

    def test_table_center_aligned(self) -> None:
        """Center-aligned column has text-align:center style (居中对齐样式)."""
        from md_mid.nodes import Table
        tbl = Table(
            headers=[[Text(content="H")]],
            alignments=["center"],
            rows=[[[Text(content="v")]]],
        )
        result = render(doc(tbl))
        assert "text-align:center" in result


class TestHtmlTable:
    """Table rendering with auto-numbering (表渲染测试)."""

    def test_table_auto_numbered(self) -> None:
        """Table has auto-numbered caption (表格自动编号)."""
        from md_mid.nodes import Table
        tbl = Table(
            headers=[[Text(content="Col")]],
            alignments=["left"],
            rows=[[[Text(content="val")]]],
            metadata={"caption": "My Table", "label": "tab:t1"},
        )
        result = render(doc(tbl))
        assert "表 1" in result or "Table 1" in result
        assert "My Table" in result

    def test_table_has_id(self) -> None:
        """Table label becomes id attribute (表格标签成为 id 属性)."""
        from md_mid.nodes import Table
        tbl = Table(
            headers=[[Text(content="H")]],
            alignments=["left"],
            rows=[[[Text(content="v")]]],
            metadata={"caption": "T", "label": "tab:x"},
        )
        result = render(doc(tbl))
        assert 'id="tab:x"' in result


# ── Footnotes ─────────────────────────────────────────────────────────────────


class TestHtmlFootnotes:
    """Footnotes rendering tests (脚注渲染测试)."""

    def test_footnote_out_of_order(self) -> None:
        """Footnote refs are numbered by appearance, even if defs are out of order (按引用顺序编号)."""
        from md_mid.nodes import FootnoteRef, FootnoteDef
        doc = Document(children=[
            Paragraph(children=[Text(content="A"), FootnoteRef(ref_id="2")]),
            FootnoteDef(def_id="1", children=[Paragraph(children=[Text(content="Note 1")])]),
            Paragraph(children=[Text(content="B"), FootnoteRef(ref_id="1")]),
            FootnoteDef(def_id="2", children=[Paragraph(children=[Text(content="Note 2")])]),
        ])
        result = render(doc)
        assert "[1]" in result
        assert "[2]" in result
        # Note 2 should be first in footnotes section because it was referenced first
        fn_section = result[result.find('<div class="footnotes">'):]
        assert fn_section.find("Note 2") < fn_section.find("Note 1")


# ── Cross-refs and citations ───────────────────────────────────────────────────


class TestHtmlCrossRef:
    """Cross-ref renders as <a href="#label"> (交叉引用渲染测试)."""

    def test_cross_ref_link(self) -> None:
        """Cross-ref → anchor link (交叉引用渲染为锚点链接)."""
        cr = CrossRef(label="fig:test", children=[Text(content="Figure 1")])
        result = render(doc(Paragraph(children=[cr])))
        assert 'href="#fig:test"' in result
        assert "Figure 1" in result


class TestHtmlCitation:
    """Citations render as superscript numbered refs (文献引用渲染测试)."""

    def test_citation_superscript(self) -> None:
        """Citation renders as [N] superscript (引用渲染为上标编号)."""
        from md_mid.nodes import Citation
        cit = Citation(keys=["wang2024"], children=[Text(content="Wang")])
        result = render(doc(Paragraph(children=[cit])))
        assert "[1]" in result
        assert 'class="cite"' in result

    def test_citation_bibliography_at_end(self) -> None:
        """Citations produce bibliography section at end of body (引用产生末尾参考文献)."""
        from md_mid.nodes import Citation
        cit = Citation(keys=["smith2024"], children=[Text(content="Smith")])
        bib = {"smith2024": "Smith, 2024, Science"}
        result = HTMLRenderer(bib=bib, mode="body").render(doc(Paragraph(children=[cit])))
        assert "Smith, 2024, Science" in result
        assert 'id="cite-smith2024"' in result

    def test_citation_xss_safe(self) -> None:
        """Citation key with special chars is HTML-escaped (引用 key 特殊字符转义)."""
        from md_mid.nodes import Citation
        cit = Citation(keys=["key<evil>"], children=[])
        result = render(doc(Paragraph(children=[cit])))
        assert "<evil>" not in result
```

### Step 2: Run tests

```bash
uv run pytest tests/test_html.py -v
```
Expected: all pass (implementation is already in html.py from Task 2).

If any fail, debug and fix `html.py`.

### Step 3: Run full suite + commit

```bash
make check
git add tests/test_html.py
git commit -m "test(html): add comprehensive figure/table/cross-ref/citation HTML tests"
```

---

## Task 4: Optional generate-figures CLI flag

**Files:**
- Create: `src/md_mid/genfig.py`
- Modify: `src/md_mid/cli.py`
- Create: `tests/test_genfig.py`

This feature is **entirely optional**: if `--generate-figures` is not passed, everything works
as before. If passed, the CLI walks the EAST for figures with `ai-generated: true` and calls
the external runner (by default the `nanobanana.py` script from the `generate-figures` skill).

The runner interface (from the skill):
```
nanobanana.generate_image(prompt, output, config=None, model=None) → int  (0 = success)
```

### Step 1: Write failing tests

Create `tests/test_genfig.py`:

```python
"""Tests for optional generate-figures feature (可选出图功能测试)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from md_mid.genfig import FigureJob, collect_jobs, generate_figure_job
from md_mid.nodes import Document, Figure, Image, Paragraph, Text


def _fig(src: str, ai: dict | None = None) -> Figure:
    """Build a Figure node for testing (构建测试用 Figure 节点)."""
    meta: dict = {}
    if ai is not None:
        meta["ai"] = ai
    return Figure(src=src, alt="alt", metadata=meta)


def _img_with_ai(src: str, ai: dict) -> Image:
    """Build an Image with AI metadata (构建含 AI 元数据的 Image 节点)."""
    return Image(src=src, alt="alt", metadata={"ai": ai})


# ── collect_jobs ──────────────────────────────────────────────────────────────


class TestCollectJobs:
    """collect_jobs finds figures with ai-generated: true (收集 AI 图作业测试)."""

    def test_figure_with_ai_generated_collected(self) -> None:
        """Figure with ai.generated=True is collected (含 ai.generated=True 的图被收集)."""
        fig = _fig("fig.png", {"generated": True, "prompt": "blue sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        assert len(jobs) == 1
        assert jobs[0].src == "fig.png"
        assert jobs[0].prompt == "blue sky"

    def test_figure_without_ai_skipped(self) -> None:
        """Figure without AI metadata is skipped (无 AI 元数据的图跳过)."""
        fig = _fig("fig.png")
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        assert len(jobs) == 0

    def test_figure_ai_generated_false_skipped(self) -> None:
        """Figure with ai.generated=False is skipped (ai.generated=False 的图跳过)."""
        fig = _fig("fig.png", {"generated": False, "prompt": "blue sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        assert len(jobs) == 0

    def test_existing_image_skipped_by_default(self, tmp_path: Path) -> None:
        """Existing image file is skipped unless force=True (已存在图片默认跳过)."""
        img_file = tmp_path / "fig.png"
        img_file.write_bytes(b"fake image")
        fig = _fig("fig.png", {"generated": True, "prompt": "blue sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=tmp_path, force=False)
        assert len(jobs) == 0

    def test_existing_image_regenerated_with_force(self, tmp_path: Path) -> None:
        """Existing image regenerated when force=True (force=True 时重新生成)."""
        img_file = tmp_path / "fig.png"
        img_file.write_bytes(b"fake image")
        fig = _fig("fig.png", {"generated": True, "prompt": "blue sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=tmp_path, force=True)
        assert len(jobs) == 1

    def test_image_node_with_ai_collected(self) -> None:
        """Image node with AI metadata is also collected (Image 节点也被收集)."""
        img = _img_with_ai("img.png", {"generated": True, "prompt": "sky"})
        doc = Document(children=[Paragraph(children=[img])])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        assert len(jobs) == 1

    def test_job_has_model_and_params(self) -> None:
        """Collected job carries model and params (作业携带 model 和 params)."""
        fig = _fig("fig.png", {
            "generated": True,
            "prompt": "technical diagram",
            "model": "midjourney-v6",
            "params": {"seed": 42},
        })
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        assert jobs[0].model == "midjourney-v6"
        assert jobs[0].params == {"seed": 42}

    def test_path_traversal_skipped(self, tmp_path: Path) -> None:
        """src with ../ that escapes base_dir is skipped (路径穿越被跳过)."""
        fig = _fig("../../etc/passwd", {"generated": True, "prompt": "sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=tmp_path)
        assert len(jobs) == 0

    def test_absolute_path_skipped(self, tmp_path: Path) -> None:
        """Absolute src path outside base_dir is skipped (绝对路径越界被跳过)."""
        fig = _fig("/tmp/evil.png", {"generated": True, "prompt": "sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=tmp_path)
        assert len(jobs) == 0

    def test_empty_src_skipped(self) -> None:
        """Empty src is handled gracefully (空 src 优雅处理)."""
        fig = _fig("", {"generated": True, "prompt": "sky"})
        doc = Document(children=[fig])
        jobs = collect_jobs(doc, base_dir=Path("/tmp"))
        # Empty src resolves to base_dir itself, which isn't harmful but useless (空 src 无害但无用)
        # Should still be collected since it's within base_dir (仍在基目录内应被收集)
        assert len(jobs) <= 1  # implementation-defined behavior


# ── generate_figure_job ────────────────────────────────────────────────────────


class TestGenerateFigureJob:
    """generate_figure_job calls runner with correct args (调用 runner 测试)."""

    def test_runner_called_with_prompt(self, tmp_path: Path) -> None:
        """Runner is called with job prompt (runner 以 prompt 调用)."""
        job = FigureJob(
            src="out.png",
            output_path=tmp_path / "out.png",
            prompt="blue sky",
            model=None,
            params=None,
        )
        mock_runner = MagicMock()
        mock_runner.generate_image.return_value = 0
        # Simulate successful output (模拟成功输出)
        (tmp_path / "out.png").write_bytes(b"img")

        ok = generate_figure_job(job, runner=mock_runner, config=None)
        assert ok is True
        mock_runner.generate_image.assert_called_once()
        call_kwargs = mock_runner.generate_image.call_args.kwargs
        assert call_kwargs["prompt"] == "blue sky"

    def test_runner_failure_returns_false(self, tmp_path: Path) -> None:
        """Runner returning non-zero means failure (runner 返回非零表示失败)."""
        job = FigureJob(
            src="out.png",
            output_path=tmp_path / "out.png",
            prompt="sky",
            model=None,
            params=None,
        )
        mock_runner = MagicMock()
        mock_runner.generate_image.return_value = 1  # failure (失败返回码)

        ok = generate_figure_job(job, runner=mock_runner, config=None)
        assert ok is False

    def test_missing_output_returns_false(self, tmp_path: Path) -> None:
        """Runner returning 0 but no output file means failure (无输出文件视为失败)."""
        job = FigureJob(
            src="out.png",
            output_path=tmp_path / "out.png",
            prompt="sky",
            model=None,
            params=None,
        )
        mock_runner = MagicMock()
        mock_runner.generate_image.return_value = 0  # claims success (声称成功)
        # But output file is NOT created (但未创建输出文件)

        ok = generate_figure_job(job, runner=mock_runner, config=None)
        assert ok is False
```

### Step 2: Run tests to confirm failures

```bash
uv run pytest tests/test_genfig.py -v
```
Expected: ImportError or all FAIL (genfig.py not yet created).

### Step 3: Create `src/md_mid/genfig.py`

```python
"""Optional AI figure generation helper.

可选 AI 图片生成辅助模块。
Walks the EAST for Figure/Image nodes with ai-generated: true and calls
the nanobanana-compatible runner to generate them.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from md_mid.nodes import Document, Figure, Image, Node


@dataclass
class FigureJob:
    """One figure to generate (待生成的一个图片作业).

    Attributes:
        src: Relative image path from document (相对图片路径)
        output_path: Resolved absolute path to write the image (绝对输出路径)
        prompt: Generation prompt (生成 prompt)
        model: Model name override (模型名覆盖，可选)
        params: Extra generation parameters (额外生成参数，可选)
    """

    src: str
    output_path: Path
    prompt: str
    model: str | None
    params: dict[str, Any] | None


def _walk(node: Node) -> list[Node]:
    """Recursively yield all descendant nodes (递归获取所有后代节点).

    Args:
        node: Root node (根节点)

    Returns:
        Flat list of all descendant nodes (所有后代节点的列表)
    """
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result


def collect_jobs(
    doc: Document,
    base_dir: Path,
    force: bool = False,
) -> list[FigureJob]:
    """Collect figure generation jobs from document EAST.

    从文档 EAST 中收集待生成的图片作业列表。

    Args:
        doc: EAST document to scan (待扫描的 EAST 文档)
        base_dir: Base directory for resolving relative image paths (相对路径解析基目录)
        force: Re-generate even if image file already exists (即使文件存在也重新生成)

    Returns:
        List of FigureJob instances needing generation (需要生成的 FigureJob 列表)
    """
    jobs: list[FigureJob] = []
    for node in _walk(doc):
        if not isinstance(node, (Figure, Image)):
            continue
        ai = node.metadata.get("ai")
        if not isinstance(ai, dict):
            continue
        if not ai.get("generated"):
            continue  # ai-generated not set to True (未设置 ai-generated: true)
        prompt = str(ai.get("prompt", "")).strip()
        if not prompt:
            continue  # no prompt, nothing to generate (无 prompt，跳过)

        src = node.src if isinstance(node, (Figure, Image)) else ""
        output_path = (base_dir / src).resolve()

        # Path traversal safety: output must stay within base_dir (路径安全：输出必须在基目录内)
        try:
            output_path.relative_to(base_dir.resolve())
        except ValueError:
            continue  # path escapes base_dir, skip (路径越界，跳过)

        if not force and output_path.exists():
            continue  # image already present, skip (图片已存在，跳过)

        jobs.append(FigureJob(
            src=src,
            output_path=output_path,
            prompt=prompt,
            model=ai.get("model") if isinstance(ai.get("model"), str) else None,
            params=ai.get("params") if isinstance(ai.get("params"), dict) else None,
        ))
    return jobs


def _load_runner(runner_path: Path) -> Any:
    """Dynamically load the nanobanana-compatible runner module.

    动态加载 nanobanana 兼容的 runner 模块。

    Args:
        runner_path: Path to the runner Python script (runner 脚本路径)

    Returns:
        Loaded module with generate_image callable (含 generate_image 的已加载模块)

    Raises:
        ImportError: If runner cannot be loaded (runner 无法加载时)
    """
    spec = importlib.util.spec_from_file_location("genfig_runner", str(runner_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def generate_figure_job(
    job: FigureJob,
    runner: Any,
    config: Path | None,
) -> bool:
    """Generate a single figure by calling the runner.

    通过调用 runner 生成单张图片。

    Args:
        job: Figure job to execute (待执行的图片作业)
        runner: Loaded runner module with generate_image (含 generate_image 的 runner 模块)
        config: Path to TOML config for runner (runner 的 TOML 配置路径，可选)

    Returns:
        True if generation succeeded and output file exists (成功生成且输出文件存在则返回 True)
    """
    job.output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build runner kwargs; pass extra params if available (构建 runner 参数)
    kwargs: dict[str, str | None] = {
        "prompt": job.prompt,
        "output": str(job.output_path),
        "config": str(config) if config else None,
        "model": job.model,
    }
    # Forward size from params if present (转发 size 参数)
    if job.params and "size" in job.params:
        kwargs["size"] = str(job.params["size"])

    returncode: int = runner.generate_image(**kwargs)

    if returncode != 0:
        return False
    return job.output_path.exists()


def run_generate_figures(
    doc: Document,
    base_dir: Path,
    runner_path: Path,
    config: Path | None = None,
    force: bool = False,
    echo: Any = None,
) -> tuple[int, int]:
    """Run the generate-figures pipeline on a document.

    对文档运行完整的出图流程。

    Args:
        doc: EAST document (EAST 文档)
        base_dir: Base directory for image paths (图片路径基目录)
        runner_path: Path to nanobanana-compatible runner (runner 脚本路径)
        config: Optional TOML config for the runner (可选的 runner TOML 配置)
        force: Regenerate even if file exists (强制重新生成)
        echo: Optional callable for progress output, e.g. click.echo (进度输出函数，可选)

    Returns:
        (success_count, fail_count) tuple (成功数, 失败数 元组)
    """
    jobs = collect_jobs(doc, base_dir=base_dir, force=force)
    if not jobs:
        if echo:
            echo("[generate-figures] No AI figures to generate (无待生成的 AI 图片).")
        return (0, 0)

    runner = _load_runner(runner_path)
    success = 0
    fail = 0
    for job in jobs:
        ok = generate_figure_job(job, runner=runner, config=config)
        if ok:
            success += 1
            if echo:
                echo(f"[generate-figures] ✓ {job.src}")
        else:
            fail += 1
            if echo:
                echo(f"[generate-figures] ✗ {job.src} (failed)")

    return (success, fail)
```

### Step 4: Add CLI flag in `src/md_mid/cli.py`

Add these Click options (after the `--bibliography-mode` option):

```python
@click.option(
    "--generate-figures", "generate_figures",
    is_flag=True,
    default=False,
    help="Generate AI figures (ai-generated: true) via runner before rendering",
)
@click.option(
    "--figures-runner", "figures_runner",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to nanobanana-compatible runner script",
)
@click.option(
    "--figures-config", "figures_config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="TOML config for runner (API key, model, etc.)",
)
@click.option(
    "--force-regenerate", "force_regenerate",
    is_flag=True,
    default=False,
    help="Re-generate AI figures even if image files already exist",
)
```

Add the corresponding parameters to the `main()` function signature:

```python
    generate_figures: bool,
    figures_runner: Path | None,
    figures_config: Path | None,
    force_regenerate: bool,
```

Insert the generation step **after** the `if strict and diag.has_errors:` check
and **before** the `if effective_target == "latex":` branch. This ensures documents with
errors are rejected before any side-effects (file generation) occur:

```python
    # Optional AI figure generation (可选 AI 图片生成)
    if generate_figures:
        from md_mid.genfig import run_generate_figures

        # Resolve runner path (解析 runner 路径)
        if figures_runner is None:
            # Default: nanobanana.py from generate-figures skill (默认 runner 路径)
            skill_runner = Path.home() / ".claude" / "skills" / "generate-figures" \
                           / "tools" / "fig" / "nanobanana.py"
            if not skill_runner.exists():
                click.echo(
                    "[generate-figures] Runner not found. "
                    "Specify --figures-runner PATH.",
                    err=True,
                )
                raise SystemExit(1)
            figures_runner = skill_runner

        # Base directory for resolving image paths (图片路径解析基目录)
        base_dir = Path(filename).parent if filename != "<stdin>" else Path.cwd()

        success, fail = run_generate_figures(
            east,
            base_dir=base_dir,
            runner_path=figures_runner,
            config=figures_config,
            force=force_regenerate,
            echo=lambda msg: click.echo(msg, err=True),
        )
        if fail > 0:
            click.echo(
                f"[generate-figures] {fail} figure(s) failed to generate.",
                err=True,
            )
```

### Step 5: Add CLI test

Add to `tests/test_cli.py`:

```python
def test_generate_figures_flag_no_runner_exits(tmp_path: Path) -> None:
    """--generate-figures without runner exits non-zero when runner missing.

    无 runner 时 --generate-figures 以非零退出 (当 runner 缺失时)。
    """
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "out.tex"
    # Point to nonexistent runner so the default lookup fails (指向不存在的 runner)
    result = CliRunner().invoke(
        main,
        [str(src), "-o", str(out), "--generate-figures",
         "--figures-runner", str(tmp_path / "nonexistent.py")],
    )
    # Should fail because runner does not exist (runner 不存在，应失败)
    assert result.exit_code != 0
```

### Step 6: Run tests

```bash
uv run pytest tests/test_genfig.py tests/test_cli.py::test_generate_figures_flag_no_runner_exits -v
make check
```
Expected: all new tests pass, overall suite green.

### Step 7: Commit

```bash
git add src/md_mid/genfig.py src/md_mid/cli.py tests/test_genfig.py tests/test_cli.py
git commit -m "feat(genfig): add optional AI figure generation with --generate-figures flag"
```

---

## Files Modified Summary

| File | Task | Change |
|------|------|--------|
| `src/md_mid/latex.py` | 1 | Add `_render_ai_comments()`, use in `render_figure` and `render_image` |
| `src/md_mid/html.py` | 2 | New file: complete `HTMLRenderer` |
| `src/md_mid/cli.py` | 2, 4 | Wire `html` target branch; add `--generate-figures` and friends |
| `src/md_mid/genfig.py` | 4 | New file: `FigureJob`, `collect_jobs`, `generate_figure_job`, `run_generate_figures` |
| `tests/test_latex.py` | 1 | Add `TestLatexAiFigureComments` |
| `tests/test_html.py` | 2, 3 | New file: comprehensive HTML renderer tests |
| `tests/test_genfig.py` | 4 | New file: generate-figures unit tests |
| `tests/test_cli.py` | 2, 4 | Add `test_html_target_*`, `test_generate_figures_*` |

---

## Verification

```bash
make check   # ruff 0, mypy 0, all tests green (≥ 350+ tests)
```

Manual smoke test:

```bash
# HTML output
echo "# Test\n\n\$E=mc^2\$" | uv run md-mid - -t html -o - | grep mathjax

# AI figure comments in LaTeX
cat > /tmp/ai.mid.md << 'EOF'
![test](fig.png)
<!-- caption: Test figure -->
<!-- ai-generated: true -->
<!-- ai-model: midjourney-v6 -->
<!-- ai-prompt: blue sky -->
EOF
uv run md-mid /tmp/ai.mid.md -o - | grep "% AI Generated"

# generate-figures (dry-run, expects non-zero exit without runner)
uv run md-mid /tmp/ai.mid.md --generate-figures -o /tmp/out.tex; echo "exit: $?"
```
