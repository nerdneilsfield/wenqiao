# Preset & Docs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `zh`/`en` built-in presets (via `<!-- preset: zh -->` directive + `--preset` CLI flag), and complete missing documentation for `package-options`, presets, and complex table / LaTeX passthrough in README, README_ZH, and SKILL.md.

**Architecture:** Presets are a new lowest-priority config layer inserted between the existing defaults and template layers. `_PRESETS` dict lives in `config.py`; `"preset"` is added as a `DOCUMENT_DIRECTIVES` key in `comment.py`; `build_config` in `pipeline.py` receives a `preset_name` argument; CLI and API each add an entry point. Docs are updated in three files.

**Priority chain after this change:**
`CLI > directives > config file > template > preset > defaults`

**Tech Stack:** Python 3.12+, click, ruamel-yaml, pytest

---

## Task 1: Add `_PRESETS` and preset layer to `config.py`

**Files:**
- Modify: `src/wenqiao/config.py`
- Test: `tests/test_config.py`

### Step 1: Write failing tests

Add to `tests/test_config.py`:

```python
# --- Preset tests (预设测试) ---

class TestPresets:
    """Tests for built-in presets (内置预设测试)."""

    def test_zh_preset_sets_ctexart(self) -> None:
        """zh preset should set documentclass to ctexart (zh 预设应设置 documentclass)."""
        cfg = resolve_config(preset_name="zh")
        assert cfg.documentclass == "ctexart"
        assert cfg.locale == "zh"

    def test_zh_preset_sets_locale_zh(self) -> None:
        """zh preset locale should be zh (zh 预设的 locale 应为 zh)."""
        cfg = resolve_config(preset_name="zh")
        assert cfg.locale == "zh"

    def test_en_preset_sets_locale_en(self) -> None:
        """en preset locale should be en (en 预设的 locale 应为 en)."""
        cfg = resolve_config(preset_name="en")
        assert cfg.locale == "en"
        assert cfg.documentclass == "article"

    def test_directive_overrides_preset(self) -> None:
        """Document directive overrides preset (文档指令应覆盖预设)."""
        cfg = resolve_config(
            preset_name="zh",
            east_meta={"documentclass": "report"},
        )
        assert cfg.documentclass == "report"
        assert cfg.locale == "zh"  # not overridden, preset value preserved

    def test_template_overrides_preset(self) -> None:
        """Template overrides preset (模板应覆盖预设)."""
        cfg = resolve_config(
            preset_name="zh",
            template_dict={"locale": "en"},
        )
        assert cfg.locale == "en"  # template wins over preset

    def test_unknown_preset_raises(self) -> None:
        """Unknown preset name should raise ValueError (未知预设应抛出 ValueError)."""
        with pytest.raises(ValueError, match="unknown preset"):
            resolve_config(preset_name="nonexistent")

    def test_none_preset_is_noop(self) -> None:
        """No preset (None) should behave like current defaults (None 预设不影响默认行为)."""
        cfg_no_preset = resolve_config()
        cfg_none = resolve_config(preset_name=None)
        assert cfg_no_preset.documentclass == cfg_none.documentclass
        assert cfg_no_preset.locale == cfg_none.locale
```

### Step 2: Run to verify they fail

```bash
uv run pytest tests/test_config.py::TestPresets -v
```
Expected: `FAILED` — `resolve_config` has no `preset_name` param yet.

### Step 3: Implement in `config.py`

Add `_PRESETS` dict after `_DEFAULTS`:

```python
# Built-in presets (内置预设字典)
_PRESETS: dict[str, dict[str, object]] = {
    "zh": {
        "documentclass": "ctexart",
        "classoptions": ["12pt", "a4paper"],
        "packages": ["amsmath", "graphicx", "hyperref"],
        "locale": "zh",
        "preamble": "% Compiled with XeLaTeX recommended (建议使用 XeLaTeX 编译)\n",
    },
    "en": {
        "documentclass": "article",
        "classoptions": ["12pt", "a4paper"],
        "packages": ["amsmath", "graphicx", "hyperref"],
        "locale": "en",
    },
}
```

Update `resolve_config` signature and body to accept `preset_name`:

```python
def resolve_config(
    cli_overrides: dict[str, object] | None = None,
    east_meta: dict[str, object] | None = None,
    config_dict: dict[str, object] | None = None,
    template_dict: dict[str, object] | None = None,
    preset_name: str | None = None,           # ← new
) -> WenqiaoConfig:
```

In the merge sequence (after starting with `_DEFAULTS`, before layering template):

```python
    # Layer preset — sits above defaults, below template (层: 预设，高于默认值，低于模板)
    if preset_name is not None:
        if preset_name not in _PRESETS:
            raise ValueError(
                f"Unknown preset {preset_name!r}; available: {list(_PRESETS)}"
                f" (未知预设 {preset_name!r}；可用预设: {list(_PRESETS)})"
            )
        merged.update(_PRESETS[preset_name])
```

### Step 4: Run tests

```bash
uv run pytest tests/test_config.py::TestPresets -v
```
Expected: all PASS.

### Step 5: Commit

```bash
git add src/wenqiao/config.py tests/test_config.py
git commit -m "feat(config): Add built-in presets zh and en with resolve_config preset_name"
```

---

## Task 2: Add `preset` to `DOCUMENT_DIRECTIVES` in `comment.py`

**Files:**
- Modify: `src/wenqiao/comment.py`
- Test: `tests/test_comment.py`

### Step 1: Write failing test

Add to `tests/test_comment.py`:

```python
def test_preset_directive_stored_in_metadata() -> None:
    """<!-- preset: zh --> should be stored in doc.metadata['preset'] (预设指令存入元数据)."""
    from wenqiao.comment import process_comments
    from wenqiao.nodes import Document, RawBlock

    doc = Document()
    doc.children = [RawBlock(content="<!-- preset: zh -->")]
    result = process_comments(doc, "<string>")
    assert result.metadata.get("preset") == "zh"
    assert len(result.children) == 0  # directive node consumed (指令节点已消费)
```

### Step 2: Run to verify fails

```bash
uv run pytest tests/test_comment.py::test_preset_directive_stored_in_metadata -v
```
Expected: FAIL — `preset` not in `DOCUMENT_DIRECTIVES`.

### Step 3: Add `"preset"` to `DOCUMENT_DIRECTIVES`

In `src/wenqiao/comment.py`, update the set:

```python
DOCUMENT_DIRECTIVES = frozenset(
    {
        "documentclass",
        "classoptions",
        "packages",
        "package-options",
        "bibliography",
        "bibstyle",
        "title",
        "author",
        "date",
        "abstract",
        "preamble",
        "latex-mode",
        "bibliography-mode",
        "preset",           # ← add this
    }
)
```

### Step 4: Run test

```bash
uv run pytest tests/test_comment.py::test_preset_directive_stored_in_metadata -v
```
Expected: PASS.

### Step 5: Commit

```bash
git add src/wenqiao/comment.py tests/test_comment.py
git commit -m "feat(comment): Recognise preset directive in header region"
```

---

## Task 3: Thread `preset_name` through `pipeline.py`

**Files:**
- Modify: `src/wenqiao/pipeline.py`
- Test: `tests/test_api.py` (integration test via `convert()`)

### Step 1: Write failing integration test

Add to `tests/test_api.py`:

```python
def test_preset_directive_zh_sets_ctexart() -> None:
    """Document with <!-- preset: zh --> should produce ctexart class (文档预设 zh)."""
    result = convert("<!-- preset: zh -->\n\n# Hello\n")
    assert "ctexart" in result.text

def test_preset_cli_overrides_preset_directive() -> None:
    """preset kwarg overrides document directive (API preset 参数覆盖文档指令)."""
    result = convert("<!-- preset: zh -->\n\n# Hello\n", preset="en")
    assert "article" in result.text
    assert "ctexart" not in result.text
```

### Step 2: Run to verify fails

```bash
uv run pytest tests/test_api.py::test_preset_directive_zh_sets_ctexart -v
```
Expected: FAIL — `build_config` doesn't pass preset to `resolve_config` yet.

### Step 3: Update `pipeline.py`

Update `build_config` to accept and thread `preset_name`:

```python
def build_config(
    east_meta: dict[str, object],
    *,
    cli_overrides: dict[str, object] | None = None,
    config_path: Path | None = None,
    template_path: Path | None = None,
    pre_built: WenqiaoConfig | None = None,
    preset_name: str | None = None,          # ← new
    diag: DiagCollector | None = None,
) -> WenqiaoConfig:
```

In the body, extract preset from east_meta if not explicitly provided, and pass to `resolve_config`:

```python
    if pre_built is not None:
        return pre_built

    tpl_dict = load_template(template_path, diag=diag) if template_path else None
    cfg_dict = load_config_file(config_path, diag=diag) if config_path else None

    # Preset: explicit arg takes priority over document directive (显式参数优先于文档指令)
    effective_preset = preset_name
    if effective_preset is None:
        doc_preset = east_meta.get("preset")
        if isinstance(doc_preset, str):
            effective_preset = doc_preset

    return resolve_config(
        cli_overrides=cli_overrides if cli_overrides else None,
        east_meta=east_meta,
        config_dict=cfg_dict,
        template_dict=tpl_dict,
        preset_name=effective_preset,
    )
```

### Step 4: Run tests

```bash
uv run pytest tests/test_api.py::test_preset_directive_zh_sets_ctexart tests/test_api.py::test_preset_cli_overrides_preset_directive -v
```
Expected: PASS.

### Step 5: Commit

```bash
git add src/wenqiao/pipeline.py tests/test_api.py
git commit -m "feat(pipeline): Thread preset_name through build_config"
```

---

## Task 4: Add `preset` parameter to `api.py`

**Files:**
- Modify: `src/wenqiao/api.py`

### Step 1: Update `convert()` signature

Add `preset: str | None = None` parameter:

```python
def convert(
    source: str | Path,
    *,
    target: str | None = None,
    mode: str | None = None,
    locale: str | None = None,
    config: WenqiaoConfig | dict[str, object] | None = None,
    template: Path | None = None,
    bib: Path | str | dict[str, str] | None = None,
    strict: bool = False,
    preset: str | None = None,    # ← new
) -> ConvertResult:
```

Pass it to `build_config`:

```python
    cfg = build_config(
        east.metadata,
        cli_overrides=cli_dict if cli_dict else None,
        template_path=template,
        pre_built=config if isinstance(config, WenqiaoConfig) else None,
        preset_name=preset,    # ← add
    )
```

Update the docstring `Args` section to include:
```
        preset: Built-in preset name — "zh" / "en" (内置预设名称)
```

### Step 2: Run full test suite

```bash
make test
```
Expected: all 532+ tests PASS.

### Step 3: Commit

```bash
git add src/wenqiao/api.py
git commit -m "feat(api): Add preset parameter to convert()"
```

---

## Task 5: Add `--preset` CLI flag to `cli.py`

**Files:**
- Modify: `src/wenqiao/cli.py`
- Test: `tests/test_cli.py`

### Step 1: Write failing CLI test

Add to `tests/test_cli.py`:

```python
def test_preset_zh_cli(tmp_path: Path, runner: CliRunner) -> None:
    """--preset zh should produce ctexart in output (CLI --preset zh 产生 ctexart)."""
    src = tmp_path / "paper.mid.md"
    src.write_text("# Hello\n")
    out = tmp_path / "paper.tex"
    result = runner.invoke(cli, ["convert", str(src), "--preset", "zh", "-o", str(out)])
    assert result.exit_code == 0
    assert "ctexart" in out.read_text()

def test_preset_unknown_cli(tmp_path: Path, runner: CliRunner) -> None:
    """--preset with unknown name should exit non-zero (未知预设应以非零码退出)."""
    src = tmp_path / "paper.mid.md"
    src.write_text("# Hello\n")
    result = runner.invoke(cli, ["convert", str(src), "--preset", "nope"])
    assert result.exit_code != 0
```

### Step 2: Run to verify fails

```bash
uv run pytest tests/test_cli.py::test_preset_zh_cli tests/test_cli.py::test_preset_unknown_cli -v
```
Expected: FAIL — `--preset` option not defined.

### Step 3: Add `--preset` option to `convert_cmd`

After the existing `--config` option in `cli.py`:

```python
@click.option(
    "--preset",
    type=click.Choice(["zh", "en"]),
    default=None,
    help="Built-in preset (内置预设): zh | en",
)
```

Add `preset: str | None` to the function signature, and pass it to `build_config`:

```python
    try:
        cfg = build_config(
            east.metadata,
            cli_overrides=cli_dict if cli_dict else None,
            config_path=config_path,
            template_path=template_path,
            preset_name=preset,    # ← add
            diag=diag,
        )
```

### Step 4: Run tests

```bash
uv run pytest tests/test_cli.py::test_preset_zh_cli tests/test_cli.py::test_preset_unknown_cli -v
```
Expected: PASS.

### Step 5: Full check

```bash
make check
```
Expected: lint + typecheck + all tests PASS.

### Step 6: Commit

```bash
git add src/wenqiao/cli.py tests/test_cli.py
git commit -m "feat(cli): Add --preset flag to convert subcommand"
```

---

## Task 6: Update README.md with package-options, presets, and complex table docs

**Files:**
- Modify: `README.md`

Three sections to add/update:

### 6a: Add `package-options` to the Document Directives section

After the existing `<!-- packages: [...] -->` example, add:

```markdown
<!-- packages: [amsmath, graphicx, geometry, inputenc] -->
<!-- package-options: {geometry: "margin=1in,top=2cm", inputenc: utf8} -->
```

Generates:
```latex
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage[margin=1in,top=2cm]{geometry}
\usepackage[utf8]{inputenc}
```

Notes:
- The value of each key is passed verbatim into `\usepackage[...]{pkg}`
- Packages listed in `package-options` but not in `packages` are emitted at the end of the preamble
- Common use cases: `geometry` for page layout, `inputenc`/`fontenc` for encodings, `xcolor` with options

### 6b: Add Presets section (new, between Configuration and Contributing)

````markdown
## Built-in Presets

Presets provide a starting-point configuration for common document types. Declare one
in the document header with a single directive — all other directives override the preset.

```markdown
<!-- preset: zh -->
<!-- title: 我的论文 -->
```

Available presets:

| Preset | `documentclass` | `locale` | Use case |
|--------|-----------------|----------|----------|
| `zh`   | `ctexart`       | `zh`     | Chinese academic paper — compile with XeLaTeX |
| `en`   | `article`       | `en`     | Standard English paper |

### Via CLI

```bash
wenqiao paper.mid.md --preset zh -o paper.tex
```

### Priority

`CLI --preset` > `<!-- preset: ... -->` directive, and both sit below templates and
document directives in the priority chain:

**CLI > directives > config file > template > preset > defaults**

So `<!-- preset: zh -->` sets `documentclass: ctexart`, but `<!-- documentclass: IEEEtran -->`
will still override it. The `--preset` flag selects *which preset to load*; individual
preset fields can always be overridden by document directives.
````

### 6c: Add Complex Tables section

After the simple table example, add a `<details>` block:

````markdown
<details>
<summary><b>Complex tables — LaTeX passthrough</b></summary>

The built-in table renderer converts GFM pipe tables to `tabular` with `\hline`.
For anything beyond that (merged cells, `booktabs`, `longtable`, `multicolumn`,
multi-row headers) use a raw LaTeX block:

```markdown
<!-- begin: raw -->
\begin{table}[htbp]
\centering
\caption{Complex multi-column table}
\label{tab:complex}
\begin{tabular}{lccc}
\hline
\multicolumn{2}{c}{Group A} & \multicolumn{2}{c}{Group B} \\
Method & Score & Method & Score \\
\hline
ICP    & 85    & NDT    & 90    \\
RANSAC & 78    & FGR    & 93    \\
\hline
\end{tabular}
\end{table}
<!-- end: raw -->
```

For `booktabs`, add `booktabs` to your packages list:

```markdown
<!-- packages: [amsmath, graphicx, booktabs] -->
```

Then use `\toprule`, `\midrule`, `\bottomrule` inside the raw block.

</details>
````

### Step 1: Make all three edits to `README.md`

### Step 2: Commit

```bash
git add README.md
git commit -m "docs(README): Add package-options, presets, and complex table docs"
```

---

## Task 7: Mirror all changes to `README_ZH.md`

**Files:**
- Modify: `README_ZH.md`

Mirror Task 6 in Chinese. Translate all three sections:
- `package-options` example with Chinese explanatory comments
- Presets section with Chinese descriptions
- Complex tables section with Chinese text

### Step 1: Edit `README_ZH.md`

### Step 2: Commit

```bash
git add README_ZH.md
git commit -m "docs(README_ZH): Add package-options, presets, and complex table docs"
```

---

## Task 8: Update `skills/wenqiao-writer/SKILL.md`

**Files:**
- Modify: `skills/wenqiao-writer/SKILL.md`

Three updates:

### 8a: Add `package-options` to Quick Reference Card

In the `HEADER` section of the card, below `<!-- packages: [...] -->`:

```
<!-- package-options: {pkg: "opts"} -->
```

### 8b: Add `preset` to Quick Reference Card

In the `HEADER` section:

```
<!-- preset: zh -->             (zh | en)
```

### 8c: Expand the `Raw LaTeX` section (Rule 9)

Extend the complex-table example and explain when to use raw blocks:

```markdown
### 9. Raw LaTeX — For complex content that cannot be expressed in Markdown

Use `<!-- begin: raw --> ... <!-- end: raw -->` for:
- **Complex tables**: merged cells, `multicolumn`, `booktabs`, `longtable`
- **Custom macros**: `\newcommand`, `\DeclareMathOperator`
- **Arbitrary LaTeX environments** not otherwise supported

**Complex table example:**
```markdown
<!-- begin: raw -->
\begin{table}[htbp]
\centering
\caption{Multi-column results}
\label{tab:complex}
\begin{tabular}{lcc}
\hline
\multicolumn{2}{c}{Performance} & Metric \\
\hline
ICP   & 85.3 & RMSE \\
Ours  & 93.1 & RMSE \\
\hline
\end{tabular}
\end{table}
<!-- end: raw -->
```

Raw blocks are transparent to Markdown renderers and HTML — they pass through verbatim.
```

### Step 1: Edit `skills/wenqiao-writer/SKILL.md`

### Step 2: Commit

```bash
git add skills/wenqiao-writer/SKILL.md
git commit -m "docs(skill): Add package-options, preset, and complex table docs"
```

---

## Task 9: Final verification

### Step 1: Run full check

```bash
make check
```
Expected: ruff, mypy, all tests PASS.

### Step 2: Smoke test presets via CLI

```bash
echo "<!-- preset: zh -->\n\n# 测试\n" | uv run wenqiao - --target latex | head -5
```
Expected: `\documentclass[12pt,a4paper]{ctexart}` in output.

```bash
echo "<!-- preset: en -->\n\n# Test\n" | uv run wenqiao - --target latex | head -5
```
Expected: `\documentclass[12pt,a4paper]{article}` with `locale: en` effects.

### Step 3: Smoke test package-options

```bash
echo "<!-- packages: [geometry] -->\n<!-- package-options: {geometry: \"margin=1in\"} -->\n\n# Hi\n" | uv run wenqiao - | head -10
```
Expected: `\usepackage[margin=1in]{geometry}` in output.

### Step 4: Final commit if any fixups needed

```bash
make check && git status
```
