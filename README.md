# md-mid

**Academic Writing Intermediate Format & Multi-target Conversion Tool**

md-mid defines a Markdown-based intermediate format for academic writing that serves as a
single source of truth for research papers. Write once in Markdown, convert to LaTeX, rich
Markdown, or self-contained HTML.

## Features

- **Multi-target output** — LaTeX (`.tex`), rich Markdown (`.md`), and HTML with MathJax
- **Citation support** — `cite`, `citep`, `citet`, `citeauthor`, `citeyear`, `textcite`,
  `parencite`, `autocite` with BibTeX file parsing
- **Math** — inline `$...$` and display `$$...$$` with labels and equation environments
- **Cross-references** — `<!-- label: sec:intro -->` and `[Section 1](ref:sec:intro)`
- **Figures & tables** — metadata via HTML comment directives (caption, label, width, placement)
- **Environments** — `<!-- begin: algorithm -->` / `<!-- end: algorithm -->` blocks
- **Include TeX** — `<!-- include-tex: fragment.tex -->` for external LaTeX fragments
- **AI figure generation** — optional pipeline with nanobanana-compatible runners
- **Configuration layers** — CLI > directives > config file > template > defaults
- **Internationalization** — `zh` and `en` locale support for labels

## Technology Stack

| Category | Tool | Version |
|----------|------|---------|
| Language | Python | >= 3.14 |
| Parser | markdown-it-py | >= 3.0 |
| Parser plugins | mdit-py-plugins | >= 0.4 |
| YAML | ruamel-yaml | >= 0.18 |
| CLI | Click | >= 8.0 |
| Build | hatchling | — |
| Package manager | uv | latest |
| Linter / Formatter | ruff | >= 0.9 |
| Type checker | mypy (strict) | >= 1.15 |
| Testing | pytest | >= 8.0 |

## Architecture

```
input.mid.md
    │
    ▼
┌──────────────────────┐
│  Markdown Parser     │  markdown-it-py + dollarmath / footnote / table plugins
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Comment Processor   │  4-phase directive extraction from HTML comments
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Enhanced AST (EAST) │  32 node types — the core data structure
└──────────┬───────────┘
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
  LaTeX  Markdown  HTML
```

Each renderer supports three output modes:

| Mode | Description |
|------|-------------|
| `full` | Complete document with preamble, `\begin{document}`, bibliography |
| `body` | Content only, inside `\begin{document}...\end{document}` |
| `fragment` | Bare content with heading degradation for embedding |

## Getting Started

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
git clone https://github.com/<owner>/academic-md2latex.git
cd academic-md2latex
uv sync
```

### Quick Start

```bash
# Markdown → LaTeX (default)
md-mid paper.mid.md -o paper.tex

# Markdown → HTML
md-mid paper.mid.md -o paper.html -t html

# Markdown → Rich Markdown
md-mid paper.mid.md -o paper.md -t markdown

# Read from stdin
cat paper.mid.md | md-mid - -o paper.tex

# Dump the Enhanced AST as JSON
md-mid paper.mid.md --dump-east
```

### CLI Options

```
Usage: md-mid [OPTIONS] INPUT

Options:
  -o, --output PATH                   Output file (stdout if omitted)
  -t, --target [latex|markdown|html]  Output format (default: latex)
  --mode [full|body|fragment]         Output scope
  --config PATH                       Config file (md-mid.yaml)
  --template PATH                     LaTeX template (.yaml)
  --bib PATH                          Bibliography file (.bib)
  --bibliography-mode MODE            auto | standalone | external | none
  --code-style [lstlisting|minted]    Code block style
  --heading-id-style [attr|html]      Heading anchor format
  --locale [zh|en]                    Output language
  --generate-figures                  Enable AI figure generation
  --figures-runner PATH               Figure generation runner script
  --figures-config PATH               Runner config (TOML)
  --force-regenerate                  Re-generate existing images
  --strict                            Strict parsing mode
  --verbose                           Verbose output
  --dump-east                         Dump Enhanced AST as JSON
  --version                           Show version
```

## Document Format

md-mid documents are standard Markdown files (`.mid.md`) with metadata encoded in HTML
comments. This keeps the source readable in any Markdown viewer while carrying full
academic semantics.

### Document-level Directives

```markdown
<!-- documentclass: article -->
<!-- classoptions: [12pt, a4paper] -->
<!-- packages: [amsmath, graphicx, hyperref] -->
<!-- bibliography: refs.bib -->
<!-- title: My Paper Title -->
<!-- author: Author Name -->
<!-- date: 2026 -->
<!-- abstract: |
  This paper presents ...
-->
```

### Citations

```markdown
Prior work [Wang et al.](cite:wang2024) showed that ...
Classical methods [1](citep:fischler1981) have limitations.
```

Supported commands: `cite`, `citep`, `citet`, `citeauthor`, `citeyear`, `textcite`,
`parencite`, `autocite`.

### Cross-references

```markdown
<!-- label: sec:intro -->
As shown in [Section 1](ref:sec:intro) ...
```

### Figures with Metadata

```markdown
![Pipeline overview](figures/pipeline.png)
<!-- caption: Point cloud registration pipeline -->
<!-- label: fig:pipeline -->
<!-- width: 0.85\textwidth -->
```

### Environments

```markdown
<!-- begin: algorithm -->
1. Initialize ...
2. Iterate ...
<!-- end: algorithm -->
```

### Full Example

See [`tests/fixtures/full_example.mid.md`](tests/fixtures/full_example.mid.md) for a
complete demonstration of all features.

## Configuration

md-mid resolves settings with a five-layer priority chain:

```
CLI flags  >  in-document directives  >  config file  >  template  >  defaults
```

### Config File (`md-mid.yaml`)

```yaml
documentclass: article
classoptions: [12pt, a4paper]
packages: [amsmath, graphicx]
code_style: lstlisting
locale: zh
target: latex
```

### Template File

Templates provide reusable defaults for specific venues:

```bash
md-mid paper.mid.md --template templates/ieee.yaml -o paper.tex
```

## Project Structure

```
academic-md2latex/
├── src/md_mid/          # Source code
│   ├── parser.py        #   Markdown → EAST parser
│   ├── nodes.py         #   EAST node definitions (32 types)
│   ├── comment.py       #   Comment directive processor
│   ├── latex.py          #   LaTeX renderer
│   ├── markdown.py       #   Rich Markdown renderer
│   ├── html.py           #   HTML renderer (MathJax)
│   ├── config.py         #   Configuration resolution
│   ├── cli.py            #   Click CLI entry point
│   ├── bibtex.py         #   BibTeX parser
│   ├── genfig.py         #   AI figure generation
│   ├── escape.py         #   LaTeX escaping utilities
│   ├── sanitize.py       #   Input sanitization
│   ├── url_check.py      #   URL safety validation
│   ├── ai_meta.py        #   Shared AI metadata rendering
│   └── diagnostic.py     #   Error/warning diagnostics
├── tests/               # Test suite (16 files, 425+ tests)
│   ├── fixtures/        #   Test markdown documents
│   └── conftest.py      #   Shared fixtures
├── templates/           # LaTeX venue templates
├── docs/                # Documentation and plans
├── pyproject.toml       # Project metadata
└── Makefile             # Build commands
```

## Development

### Setup

```bash
uv sync                  # Install all dependencies
```

### Commands

```bash
make check               # Run lint + typecheck + test (use before committing)
make test                # Run pytest
make lint                # Run ruff linter
make format              # Run ruff formatter
make typecheck           # Run mypy (strict mode)
make fix                 # Auto-fix lint issues + format
```

### Coding Standards

- **Type annotations** — required on all functions and methods
- **Bilingual comments** — English + Chinese: `# Calculate average (计算平均值)`
- **Docstrings** — Google style with bilingual descriptions
- **Line length** — 100 characters max
- **Naming** — `snake_case` for functions/modules, `PascalCase` for classes,
  `UPPER_SNAKE_CASE` for constants

### Testing

Tests mirror source modules one-to-one. Run the full suite:

```bash
make test
```

Test naming convention: `test_<function>_<scenario>`.

Test fixtures in `tests/fixtures/` provide reusable `.mid.md` documents covering
headings, math, citations, cross-references, comments, and full multi-feature examples.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests first (TDD encouraged)
4. Ensure `make check` passes (ruff, mypy, pytest)
5. Submit a pull request

All code must include complete type annotations and bilingual comments.
