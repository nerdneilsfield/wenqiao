"""Tests for HTML renderer (HTML 渲染器测试)."""

from __future__ import annotations

from md_mid.html import HTMLRenderer
from md_mid.nodes import (
    Blockquote,
    Citation,
    CodeBlock,
    CodeInline,
    CrossRef,
    Document,
    Emphasis,
    Figure,
    HardBreak,
    Heading,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    RawBlock,
    SoftBreak,
    Strong,
    Table,
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
    """Heading renders to h1-h6 with id anchor (标题渲染为带 id 的 h 标签)."""

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
    """Paragraph renders to p tag (段落渲染为 p 标签)."""

    def test_basic_paragraph(self) -> None:
        result = render(doc(Paragraph(children=[Text(content="Hello world")])))
        assert "<p>" in result
        assert "Hello world" in result


class TestHtmlList:
    """Lists render to ul/ol (列表渲染)."""

    def test_unordered_list(self) -> None:
        lst = List(
            ordered=False,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="item")])]),
            ],
        )
        result = render(doc(lst))
        assert "<ul>" in result
        assert "<li>" in result

    def test_ordered_list(self) -> None:
        lst = List(
            ordered=True,
            children=[
                ListItem(children=[Paragraph(children=[Text(content="item")])]),
            ],
        )
        result = render(doc(lst))
        assert "<ol>" in result


class TestHtmlCodeBlock:
    """Code block renders to pre/code (代码块渲染)."""

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
    """Blockquote renders to blockquote tag (引用渲染)."""

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
        assert "x^2 + y^2 = z^2" in result

    def test_math_inline(self) -> None:
        p = Paragraph(
            children=[
                Text(content="See "),
                MathInline(content="E=mc^2"),
            ]
        )
        result = render(doc(p))
        assert "E=mc^2" in result


class TestHtmlThematicBreak:
    """Thematic break renders to hr (分割线渲染)."""

    def test_thematic_break(self) -> None:
        result = render(doc(ThematicBreak()))
        assert "<hr" in result


class TestHtmlRawBlock:
    """Raw block HTML passthrough; LaTeX raw block as details fold (原始块处理)."""

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
        p = Paragraph(children=[Link(url="https://example.com", children=[Text(content="click")])])
        result = render(doc(p))
        assert 'href="https://example.com"' in result
        assert "click" in result

    def test_text_xss_escaped(self) -> None:
        p = Paragraph(children=[Text(content="<script>alert(1)</script>")])
        result = render(doc(p), mode="fragment")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_hard_break(self) -> None:
        p = Paragraph(children=[Text(content="a"), HardBreak(), Text(content="b")])
        result = render(doc(p))
        assert "<br" in result

    def test_soft_break_renders_newline(self) -> None:
        """SoftBreak renders as newline (软换行渲染为换行)."""
        p = Paragraph(children=[Text(content="a"), SoftBreak(), Text(content="b")])
        result = render(doc(p))
        assert "a\nb" in result

    def test_cross_ref_uses_display_text(self) -> None:
        """CrossRef uses display_text, not children (交叉引用使用 display_text)."""
        cr = CrossRef(label="fig:test", display_text="Figure 1")
        result = render(doc(Paragraph(children=[cr])))
        assert "Figure 1" in result
        assert 'href="#fig:test"' in result

    def test_link_javascript_scheme_sanitized(self) -> None:
        """Links with javascript: scheme are sanitized (javascript: 链接被过滤)."""
        p = Paragraph(children=[Link(url="javascript:alert(1)", children=[Text(content="click")])])
        result = render(doc(p))
        assert "javascript:" not in result

    def test_math_inline_html_escaped(self) -> None:
        """Inline math with script is HTML-escaped (数学公式 HTML 转义)."""
        p = Paragraph(children=[MathInline(content="x<script>alert(1)</script>y")])
        result = render(doc(p), mode="fragment")
        assert "<script>" not in result


# ── Figures and tables ────────────────────────────────────────────────────────


class TestHtmlFigure:
    """Figure rendering with auto-numbering and AI details (图渲染测试)."""

    def test_figure_auto_numbered(self) -> None:
        """Two figures get sequential numbers (两图自动编号)."""
        fig1 = Figure(src="a.png", alt="A", metadata={"caption": "First", "label": "fig:a"})
        fig2 = Figure(src="b.png", alt="B", metadata={"caption": "Second", "label": "fig:b"})
        result = render(doc(fig1, fig2))
        # Check auto-numbering regardless of locale (检查自动编号，不限语言)
        assert "图 1" in result or "Figure 1" in result
        assert "图 2" in result or "Figure 2" in result

    def test_figure_has_id_anchor(self) -> None:
        """Figure label becomes id attribute (标签成为 id 属性)."""
        fig = Figure(src="a.png", alt="A", metadata={"caption": "Cap", "label": "fig:test"})
        result = render(doc(fig))
        assert 'id="fig:test"' in result

    def test_figure_ai_details(self) -> None:
        """Figure with AI metadata shows details block (AI 信息折叠块)."""
        fig = Figure(
            src="a.png",
            alt="A",
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
        """Chinese locale uses '图 N' prefix (中文标签前缀测试)."""
        fig = Figure(src="a.png", alt="A", metadata={"caption": "Cap"})
        result = HTMLRenderer(locale="zh").render(doc(fig))
        assert "图 1" in result


class TestHtmlLangAttribute:
    """html lang respects locale setting (lang 属性随 locale 变化)."""

    def test_html_lang_en(self) -> None:
        """locale=en → lang='en' (英文模式 lang 属性)."""
        result = HTMLRenderer(locale="en").render(doc(Paragraph(children=[Text(content="Hi")])))
        assert 'lang="en"' in result

    def test_html_lang_zh(self) -> None:
        """locale=zh → lang='zh-CN' (中文模式 lang 属性)."""
        result = HTMLRenderer(locale="zh").render(doc(Paragraph(children=[Text(content="Hi")])))
        assert 'lang="zh-CN"' in result


class TestHtmlTableAlignment:
    """Table cell alignment respects column alignments (表格列对齐测试)."""

    def test_table_center_aligned(self) -> None:
        """Center-aligned column has text-align:center style (居中对齐样式)."""
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
        tbl = Table(
            headers=[[Text(content="Col")]],
            alignments=["left"],
            rows=[[[Text(content="val")]]],
            metadata={"caption": "My Table", "label": "tab:t1"},
        )
        result = render(doc(tbl))
        # Check auto-numbering regardless of locale (检查自动编号，不限语言)
        assert "表 1" in result or "Table 1" in result
        assert "My Table" in result

    def test_table_has_id(self) -> None:
        """Table label becomes id attribute (表格标签成为 id 属性)."""
        tbl = Table(
            headers=[[Text(content="H")]],
            alignments=["left"],
            rows=[[[Text(content="v")]]],
            metadata={"caption": "T", "label": "tab:x"},
        )
        result = render(doc(tbl))
        assert 'id="tab:x"' in result


# ── Cross-refs and citations ─────────────────────────────────────────────────


class TestHtmlCrossRef:
    """Cross-ref renders as anchor link (交叉引用渲染测试)."""

    def test_cross_ref_link(self) -> None:
        """Cross-ref → anchor link (交叉引用渲染为锚点链接)."""
        cr = CrossRef(label="fig:test", display_text="Figure 1")
        result = render(doc(Paragraph(children=[cr])))
        assert 'href="#fig:test"' in result
        assert "Figure 1" in result


class TestHtmlCitation:
    """Citations render as superscript numbered refs (文献引用渲染测试)."""

    def test_citation_superscript(self) -> None:
        """Citation renders as [N] superscript (引用渲染为上标编号)."""
        cit = Citation(keys=["wang2024"])
        result = render(doc(Paragraph(children=[cit])))
        assert "[1]" in result
        assert 'class="cite"' in result

    def test_citation_bibliography_at_end(self) -> None:
        """Citations produce bibliography section at end of body (引用产生末尾参考文献)."""
        cit = Citation(keys=["smith2024"])
        bib = {"smith2024": "Smith, 2024, Science"}
        result = HTMLRenderer(bib=bib, mode="body").render(doc(Paragraph(children=[cit])))
        assert "Smith, 2024, Science" in result
        assert 'id="cite-smith2024"' in result

    def test_citation_xss_safe(self) -> None:
        """Citation key with special chars is HTML-escaped (引用 key 特殊字符转义)."""
        cit = Citation(keys=["key<evil>"])
        result = render(doc(Paragraph(children=[cit])))
        assert "<evil>" not in result
