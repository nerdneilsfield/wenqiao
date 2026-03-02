from md_mid.markdown import MarkdownRenderer
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
    Table,
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
