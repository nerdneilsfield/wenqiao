from pathlib import Path

from md_mid.nodes import (
    Document, Heading, Paragraph, Text, Strong, Emphasis,
    MathInline, MathBlock, List, ListItem, Blockquote,
    CodeInline, SoftBreak, Citation, CrossRef,
)
from md_mid.parser import parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_returns_document():
    doc = parse("# Hello")
    assert isinstance(doc, Document)


def test_heading():
    doc = parse("# Hello World")
    assert len(doc.children) == 1
    h = doc.children[0]
    assert isinstance(h, Heading)
    assert h.level == 1
    texts = [c for c in h.children if isinstance(c, Text)]
    assert any("Hello World" in t.content for t in texts)


def test_paragraph_with_inline():
    doc = parse("This is **bold** and *italic*.")
    para = doc.children[0]
    assert isinstance(para, Paragraph)
    # 段落应包含 Text, Strong, Text, Emphasis, Text
    types = [type(c).__name__ for c in para.children]
    assert "Strong" in types
    assert "Emphasis" in types


def test_math_inline():
    doc = parse("Hello $E=mc^2$ world")
    para = doc.children[0]
    math_nodes = [c for c in para.children if isinstance(c, MathInline)]
    assert len(math_nodes) == 1
    assert math_nodes[0].content == "E=mc^2"


def test_math_block():
    doc = parse("$$\n\\int_0^\\infty f(x) dx\n$$")
    math_nodes = [c for c in doc.children if isinstance(c, MathBlock)]
    assert len(math_nodes) == 1
    assert "\\int" in math_nodes[0].content


def test_unordered_list():
    doc = parse("- a\n- b\n")
    lst = doc.children[0]
    assert isinstance(lst, List)
    assert lst.ordered is False
    assert len(lst.children) == 2
    assert all(isinstance(c, ListItem) for c in lst.children)


def test_blockquote():
    doc = parse("> hello\n")
    bq = doc.children[0]
    assert isinstance(bq, Blockquote)


def test_code_inline():
    doc = parse("use `printf`")
    para = doc.children[0]
    codes = [c for c in para.children if isinstance(c, CodeInline)]
    assert len(codes) == 1
    assert codes[0].content == "printf"


def test_fixture_minimal(tmp_path):
    text = (FIXTURES / "minimal.mid.md").read_text()
    doc = parse(text)
    assert isinstance(doc, Document)
    # 应至少有: heading, paragraph, math_block, list, blockquote
    types = {type(c).__name__ for c in doc.children}
    assert "Heading" in types
    assert "Paragraph" in types
    assert "MathBlock" in types
    assert "List" in types
    assert "Blockquote" in types


# ── cite/ref tests (Task 10) ──────────────────────────────────


def test_cite_single():
    doc = parse("[Wang et al.](cite:wang2024)")
    para = doc.children[0]
    cites = [c for c in para.children if isinstance(c, Citation)]
    assert len(cites) == 1
    assert cites[0].keys == ["wang2024"]
    assert cites[0].display_text == "Wang et al."


def test_cite_multiple_keys():
    doc = parse("[1-3](cite:wang2024,li2023,zhang2025)")
    para = doc.children[0]
    cites = [c for c in para.children if isinstance(c, Citation)]
    assert len(cites) == 1
    assert cites[0].keys == ["wang2024", "li2023", "zhang2025"]


def test_cite_empty_display():
    doc = parse("[](cite:wang2024)")
    para = doc.children[0]
    cites = [c for c in para.children if isinstance(c, Citation)]
    assert len(cites) == 1
    assert cites[0].display_text == ""


def test_cite_with_cmd():
    doc = parse("[Wang](cite:wang2024?cmd=citeauthor)")
    para = doc.children[0]
    cites = [c for c in para.children if isinstance(c, Citation)]
    assert len(cites) == 1
    assert cites[0].cmd == "citeauthor"


def test_ref():
    doc = parse("[图1](ref:fig:result)")
    para = doc.children[0]
    refs = [c for c in para.children if isinstance(c, CrossRef)]
    assert len(refs) == 1
    assert refs[0].label == "fig:result"
    assert refs[0].display_text == "图1"


def test_regular_link_not_converted():
    doc = parse("[click](http://example.com)")
    para = doc.children[0]
    from md_mid.nodes import Link
    links = [c for c in para.children if isinstance(c, Link)]
    assert len(links) == 1
