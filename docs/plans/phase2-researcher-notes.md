# Phase 2: Researcher Notes for Coder & Tester

## Section 1: LaTeX -> Markdown Pattern Mapping

The `MarkdownRenderer` in `src/md_mid/markdown.py` mirrors `LaTeXRenderer` in `src/md_mid/latex.py`.
All render methods use underscore-prefix private convention: `_render_<node_type>`.

| LaTeX method (`latex.py`) | Markdown method (`markdown.py`) | Output format |
|---|---|---|
| `render_heading()` | `_render_heading()` | `## Text {#label}` (attr) or `<h2 id="label">Text</h2>` (html) |
| `render_paragraph()` | `_render_paragraph()` | `text\n\n` — also detects Image-in-Paragraph for figure promotion |
| `render_text()` | `_render_text()` | Raw content (NO escaping, unlike LaTeX) |
| `render_strong()` | `_render_strong()` | `**text**` |
| `render_emphasis()` | `_render_emphasis()` | `*text*` |
| `render_code_inline()` | `_render_code_inline()` | `` `code` `` |
| `render_math_inline()` | `_render_math_inline()` | `$math$` |
| `render_link()` | `_render_link()` | `[text](url)` |
| `render_softbreak()` | `_render_softbreak()` | `\n` |
| `render_hardbreak()` | `_render_hardbreak()` | `  \n` (two trailing spaces) |
| `render_citation()` | `_render_citation()` | `display_text[^key1][^key2]` |
| `render_cross_ref()` | `_render_cross_ref()` | `<a href="#label">display_text</a>` |
| `render_footnote_ref()` | `_render_footnote_ref()` | `[^ref_id]` |
| `render_footnote_def()` | `_render_footnote_def()` | `""` (skipped; collected at document end) |
| `render_math_block()` | `_render_math_block()` | `$$\ncontent\n$$` with optional `<a id="label">` anchor |
| `render_code_block()` | `_render_code_block()` | ` ```lang\ncontent\n``` ` |
| `render_list()` | `_render_list()` | `- item` (unordered) or `1. item` (ordered) |
| `render_list_item()` | `_render_list_item()` | Stripped children content |
| `render_blockquote()` | `_render_blockquote()` | `> text` per line |
| `render_figure()` | `_render_figure()` | HTML `<figure>` block with `<figcaption>` |
| `render_image()` | `_render_image()` | `![alt](src)` inline, or promoted to figure |
| `render_table()` | `_render_table()` | HTML `<figure><table>` with `<figcaption>` |
| `render_raw_block()` | `_render_raw_block()` | `<details>` fold with ```` ```latex ```` block |
| `render_environment()` | `_render_environment()` | Just renders children (no env wrapping) |
| `render_thematic_break()` | `_render_thematic_break()` | `---\n\n` |
| `render_document()` | `_render_document()` | Children only (top-level `render()` handles front matter + footnotes) |

Key structural difference: LaTeX `render()` dispatches via public `render_<type>()`.
Markdown uses private `_dispatch()` -> `_render_<type>()`. The public entry point is `render(doc)`.

## Section 2: Critical Implementation Notes

### Two-Pass Architecture

- **Pass 1 (`_build_index`)**: Walks entire tree, collects Citation keys in order into `MarkdownIndex.cite_keys` (unique, ordered). Nothing else is collected in Pass 1 -- figure/table numbering happens in Pass 2.
- **Pass 2 (`render` method)**: Renders front matter, body (via `_render_children`), then appends footnote definitions at end.

### Image-in-Paragraph Figure Detection

In `_render_paragraph()`, check:
1. `len(p.children) == 1`
2. `isinstance(p.children[0], Image)`
3. Image has `"caption"` or `"label"` in `metadata`

If all true -> call `_render_image_as_figure(img)` instead of normal paragraph rendering.
If not -> render as normal paragraph text.

Plain `Image` nodes without caption/label render as `![alt](src)` inline markdown.

### Figure vs Table Counters

- `self._fig_count` increments in `_render_figure_block()` (used by both Figure nodes and promoted Images)
- `self._tab_count` increments in `_render_table()`
- They are **independent** -- first figure is always "1", first table is always "1"
- Both reset to 0 at the start of each `render()` call

### No LaTeX Escaping

`_render_text()` returns `cast(Text, node).content` directly -- no escaping.
This is different from `latex.py` which calls `escape_latex_with_protection()`.

### Footnote Definitions at Document End

`_render_footnotes()` is called after body rendering in the top-level `render()` method.
It outputs `[^key]: content` for each key in `self._index.cite_keys`.
Content comes from `self._bib` dict if available, otherwise falls back to the key itself.
`_render_footnote_def()` returns empty string -- definitions are NOT rendered inline.

### Constructor Parameters

```python
MarkdownRenderer(
    bib: dict[str, str] | None = None,       # cite key -> formatted string
    heading_id_style: str = "attr",           # "attr" ({#id}) or "html" (<hN id=...>)
    diag: DiagCollector | None = None,
)
```

### AI Info in Figures

If `metadata["ai"]` is a dict, figure blocks include a `<details>` fold with model/prompt/negative_prompt/params fields.

## Section 3: Code Quality Standards

From CLAUDE.md -- all code must follow:

1. **Type annotations**: ALL functions/methods MUST have complete type annotations
2. **`from __future__ import annotations`**: Required at top of every module
3. **Bilingual comments**: ALL comments must be `English (中文)` format
4. **Docstrings**: Google style, bilingual, with Args/Returns/Raises
5. **Line length**: Max 88 chars (ruff enforces)
6. **Naming**: snake_case functions, PascalCase classes, UPPER_SNAKE constants

### Verification commands

```bash
uv run ruff check src/md_mid/markdown.py tests/test_markdown.py
uv run mypy src/md_mid/markdown.py
uv run pytest tests/test_markdown.py -v
```

## Section 4: Test Patterns

### From `tests/test_latex.py`

- Tests organized in classes by category: `TestInline`, `TestBlock`, `TestCiteRef`, `TestFullDocument`, `TestBodyMode`, `TestFragmentMode`, `TestFigure`, `TestTable`, `TestDiagnostics`
- Module-level helpers:

```python
def render(node, **kwargs):
    return MarkdownRenderer(**kwargs).render(node)

def doc(*children):
    return Document(children=list(children))
```

- Tests wrap nodes in `doc(Paragraph(children=[...]))` for inline tests (since `render()` expects a `Document`)
- Block nodes: `doc(Heading(...))`, `doc(CodeBlock(...))`, etc.
- Metadata set directly: `node.metadata["label"] = "sec:intro"`
- Assertions use `in` checks for flexibility: `assert "## Title" in result`

### Node imports needed (from `nodes.py`)

Block: `Document`, `Heading`, `Paragraph`, `Blockquote`, `List`, `ListItem`, `CodeBlock`, `MathBlock`, `Figure`, `Table`, `Environment`, `RawBlock`, `ThematicBreak`

Inline: `Text`, `Strong`, `Emphasis`, `CodeInline`, `MathInline`, `Link`, `Image`, `Citation`, `CrossRef`, `FootnoteRef`, `FootnoteDef`, `SoftBreak`, `HardBreak`

### CLI test patterns (from `tests/test_cli.py`)

- Uses `CliRunner` from `click.testing`
- Tests create temp files in `tmp_path`, invoke CLI, check exit code and output content
- Pattern: write `.mid.md` file, invoke with `-t markdown -o <out>`, read and assert output

### Existing fixtures

Located in `tests/fixtures/`. The E2E test references `full_example.mid.md`.
