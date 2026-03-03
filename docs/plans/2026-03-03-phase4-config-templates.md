# Phase 4: Configuration, Templates & Remaining Directives

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a unified configuration system with priority resolution, LaTeX template support, and remaining PRD directives (`include-tex`, configurable code/thematic-break styles, environment args list, LaTeX footnote rendering).

**Architecture:** Configuration resolution uses a **dict-based layered merge** approach. Each config source (defaults, template, config file, document directives, CLI args) produces a plain `dict[str, object]` containing **only the keys it explicitly sets**. Layers are merged bottom-up via `dict.update()`: `defaults | template | config_file | doc_directives | cli_args`. The final merged dict is converted to a `MdMidConfig` dataclass at the end. This avoids the "compare to default" problem — each layer's dict simply **doesn't include** keys it hasn't set, so `dict.update()` naturally preserves lower-priority values. Renderers continue to accept individual keyword params (not a config object), maintaining backward compatibility with existing tests. The CLI wires up the resolution pipeline and passes resolved values to renderers.

**Tech Stack:** Python 3.14, ruamel.yaml (already a dependency), click, dataclasses, pathlib

---

## PRD Phase 4 Alignment

| PRD Section | Feature | Status |
|---|---|---|
| SS10.1 | Config priority chain | This plan (Task 1-3) |
| SS10.2 | External config file (`md-mid.yaml`) | Task 2 |
| SS10.3 | LaTeX template files (`.yaml`) | Task 3 |
| SS9 | CLI `--template`, `--config`, `--bibliography-mode` | Task 4 |
| SS10.2 | `code-style: lstlisting \| minted` | Task 5 |
| SS10.2 | `thematic-break: newpage \| hrule \| ignore` | Task 6 |
| SS4.2.2 | `include-tex` directive | Task 7 |
| SS11 | Environment `args` as YAML list -> `{arg1}{arg2}` | Task 8 |
| SS5.3 | LaTeX footnote two-pass rendering | Task 9 |
| Phase 3 deferred | LaTeX locale (`\figurename` etc.) | Task 10 |

---

## Dependency Graph

```
Task 1 (Config dataclass + resolve)
  |---> Task 2 (Config file loader) ---> Task 3 (Template loader) ---> Task 4 (CLI integration)
  |---> Task 5 (Code style) ---- depends on Task 4 (config flows to renderer)
  |---> Task 6 (Thematic break) - depends on Task 4
  L---> Task 10 (LaTeX locale) -- depends on Task 4

Task 7 (include-tex) -------- independent
Task 8 (Env args list) ------ independent
Task 9 (LaTeX footnotes) ---- independent
```

**Recommended order:** 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10

Tasks 7-9 are independent and can be parallelized.

---

## Task 1: Config Dataclass and Dict-Based Resolution

**Files:**
- Create: `src/md_mid/config.py`
- Test: `tests/test_config.py`

This task defines the central `MdMidConfig` dataclass and the `resolve_config()` function
that merges plain dicts in priority order.

**Design rationale (from code review):** The original plan used an `_UNSET` sentinel and
a `merge()` method that compared overlay values to defaults. This is fundamentally broken:
it cannot distinguish "explicitly set to the default value" from "not set at all". The
dict-based approach avoids this entirely — each config source produces a dict with **only**
the keys it explicitly sets. `dict.update()` naturally preserves lower-priority values for
absent keys.

**List/dict merge strategy:** Higher-priority layers **replace** (not append) list/dict
values from lower layers. For example, if the template sets `packages: [amsmath, cite]`,
it replaces the default `[amsmath, graphicx]`. This is simple, predictable, and consistent
with `dict.update()` semantics.

**Step 1: Write the failing test**

In `tests/test_config.py`:

```python
from pathlib import Path

from md_mid.config import MdMidConfig, resolve_config


def test_config_defaults() -> None:
    """Default config values match PRD SS10.2 (默认配置值)."""
    cfg = MdMidConfig()
    assert cfg.target == "latex"
    assert cfg.mode == "full"
    assert cfg.documentclass == "article"
    assert cfg.classoptions == ["12pt", "a4paper"]
    assert "amsmath" in cfg.packages
    assert cfg.bibstyle == "plain"
    assert cfg.code_style == "lstlisting"
    assert cfg.thematic_break == "newpage"
    assert cfg.ref_tilde is True
    assert cfg.heading_id_style == "attr"
    assert cfg.locale == "zh"
    assert cfg.bibliography_mode == "auto"


def test_config_from_dict() -> None:
    """Build config from dict with kebab-to-snake normalization (从字典构建配置)."""
    d = {"mode": "fragment", "code-style": "minted", "ref-tilde": False}
    cfg = MdMidConfig.from_dict(d)
    assert cfg.mode == "fragment"
    assert cfg.code_style == "minted"
    assert cfg.ref_tilde is False


def test_config_from_dict_ignores_unknown() -> None:
    """Unknown keys are ignored (未知键被忽略)."""
    d = {"mode": "body", "unknown-key": "value"}
    cfg = MdMidConfig.from_dict(d)
    assert cfg.mode == "body"


def test_resolve_config_priority_chain() -> None:
    """Config priority chain: CLI > doc > config > template > defaults (优先级链)."""
    cfg = resolve_config(
        cli_overrides={"mode": "body"},
        east_meta={"documentclass": "report"},
        config_dict={"code-style": "minted"},
        template_dict={"bibstyle": "IEEEtran"},
    )
    assert cfg.mode == "body"          # from CLI (来自 CLI)
    assert cfg.documentclass == "report"  # from doc directives (来自文档指令)
    assert cfg.code_style == "minted"  # from config file (来自配置文件)
    assert cfg.bibstyle == "IEEEtran"  # from template (来自模板)
    assert cfg.target == "latex"       # from defaults (来自默认值)


def test_resolve_config_higher_priority_wins() -> None:
    """Higher priority overrides lower (高优先级覆盖低优先级)."""
    cfg = resolve_config(
        cli_overrides={"mode": "fragment"},
        east_meta={"mode": "body"},
    )
    assert cfg.mode == "fragment"  # CLI wins over doc directive


def test_resolve_config_explicit_default_preserved() -> None:
    """Explicitly set default value is preserved, not clobbered (显式默认值保留)."""
    # CLI explicitly sets mode="full" (which is also the default)
    # Template sets mode="body"
    # CLI should win even though its value equals the default
    cfg = resolve_config(
        cli_overrides={"mode": "full"},
        template_dict={"mode": "body"},
    )
    assert cfg.mode == "full"  # CLI wins, even though "full" is default
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'md_mid.config'`

**Step 3: Write minimal implementation**

In `src/md_mid/config.py`:

```python
"""Unified configuration for md-mid.

统一配置对象，实现 PRD SS10.1 优先级链：
CLI args > document directives > external config > template > defaults.

Architecture: dict-based layered merge. Each config source produces a plain dict
with only the keys it explicitly sets. Layers merge via dict.update().
(架构：基于字典的分层合并。每个配置源仅产出显式设置的键值对。)
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


# Default config values matching PRD SS10.2 (PRD SS10.2 默认值)
_DEFAULTS: dict[str, object] = {
    "target": "latex",
    "mode": "full",
    "documentclass": "article",
    "classoptions": ["12pt", "a4paper"],
    "packages": ["amsmath", "graphicx"],
    "package_options": {},
    "bibliography": "",
    "bibstyle": "plain",
    "bibliography_mode": "auto",
    "code_style": "lstlisting",
    "thematic_break": "newpage",
    "ref_tilde": True,
    "title": "",
    "author": "",
    "date": "",
    "abstract": "",
    "preamble": "",
    "heading_id_style": "attr",
    "locale": "zh",
    "strict": False,
    "verbose": False,
}


@dataclass
class MdMidConfig:
    """Central configuration object (中央配置对象).

    Attributes follow PRD SS10.2 naming (snake_case internally, kebab-case externally).
    This is the **resolved** config — all layers already merged.
    """

    # Output options (输出选项)
    target: str = "latex"
    mode: str = "full"

    # LaTeX options (LaTeX 选项)
    documentclass: str = "article"
    classoptions: list[str] = field(default_factory=lambda: ["12pt", "a4paper"])
    packages: list[str] = field(default_factory=lambda: ["amsmath", "graphicx"])
    package_options: dict[str, str] = field(default_factory=dict)
    bibliography: str = ""
    bibstyle: str = "plain"
    bibliography_mode: str = "auto"
    code_style: str = "lstlisting"       # lstlisting | minted
    thematic_break: str = "newpage"      # newpage | hrule | ignore
    ref_tilde: bool = True

    # Document metadata populated by directives (文档元信息，由指令填充)
    title: str = ""
    author: str = ""
    date: str = ""
    abstract: str = ""
    preamble: str = ""

    # Markdown options (Markdown 选项)
    heading_id_style: str = "attr"       # attr | html
    locale: str = "zh"                   # zh | en

    # Runtime flags (运行时标志，非序列化)
    strict: bool = False
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MdMidConfig:
        """Build config from dict with kebab/snake key normalization (从字典构建配置).

        Args:
            data: Dictionary with kebab-case or snake_case keys (键可为 kebab 或 snake)

        Returns:
            MdMidConfig with matched fields set, defaults for missing (匹配字段已设置)
        """
        valid_fields = {f.name for f in fields(cls)}
        kwargs: dict[str, object] = {}
        for key, value in data.items():
            norm = key.replace("-", "_")
            if norm in valid_fields:
                kwargs[norm] = value
        return cls(**kwargs)  # type: ignore[arg-type]


def resolve_config(
    cli_overrides: dict[str, object] | None = None,
    east_meta: dict[str, object] | None = None,
    config_dict: dict[str, object] | None = None,
    template_dict: dict[str, object] | None = None,
) -> MdMidConfig:
    """Resolve final config by merging dict layers in priority order (按优先级合并配置).

    Priority (high -> low): CLI > document directives > config file > template > defaults.
    Each layer is a plain dict with only the keys it explicitly sets.
    dict.update() naturally preserves lower-priority values for absent keys.

    Args:
        cli_overrides: CLI arg overrides, only non-None values (CLI 覆盖)
        east_meta: Document directive metadata (文档指令元数据)
        config_dict: Flattened config file dict (配置文件)
        template_dict: Template file dict (模板文件)

    Returns:
        Fully resolved MdMidConfig (完全解析的配置)
    """
    # Start with defaults (从默认值开始)
    merged: dict[str, object] = _DEFAULTS.copy()
    # Deep copy mutable defaults (深拷贝可变默认值)
    merged["classoptions"] = list(_DEFAULTS["classoptions"])  # type: ignore[arg-type]
    merged["packages"] = list(_DEFAULTS["packages"])  # type: ignore[arg-type]
    merged["package_options"] = dict(_DEFAULTS["package_options"])  # type: ignore[arg-type]

    # Layer template (层: 模板)
    if template_dict:
        merged.update(_normalize_keys(template_dict))

    # Layer config file (层: 配置文件)
    if config_dict:
        merged.update(_normalize_keys(config_dict))

    # Layer document directives (层: 文档指令)
    if east_meta:
        merged.update(_normalize_keys(east_meta))

    # Layer CLI overrides — highest priority (层: CLI 参数，最高优先级)
    if cli_overrides:
        merged.update(_normalize_keys(cli_overrides))

    return MdMidConfig.from_dict(merged)


def _normalize_keys(data: dict[str, object]) -> dict[str, object]:
    """Normalize kebab-case keys to snake_case (将 kebab-case 键归一化为 snake_case)."""
    return {k.replace("-", "_"): v for k, v in data.items()}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/md_mid/config.py tests/test_config.py
git commit -m "feat(config): add MdMidConfig dataclass with dict-based layered resolution"
```

---

## Task 2: External Config File Loader

**Files:**
- Modify: `src/md_mid/config.py` -- Add `load_config_file()`
- Test: `tests/test_config.py` -- Config file loading tests

**Step 1: Write the failing test**

In `tests/test_config.py`:

```python
from md_mid.config import load_config_file


def test_load_config_file(tmp_path: Path) -> None:
    """Load external config file (加载外部配置文件)."""
    cfg_file = tmp_path / "md-mid.yaml"
    cfg_file.write_text(
        "latex:\n"
        "  mode: body\n"
        "  code-style: minted\n"
        "  bibstyle: IEEEtran\n"
        "markdown:\n"
        "  locale: en\n"
    )
    d = load_config_file(cfg_file)
    assert d["mode"] == "body"
    assert d["code-style"] == "minted"
    assert d["bibstyle"] == "IEEEtran"
    assert d["locale"] == "en"


def test_load_config_file_not_found() -> None:
    """Missing config file returns empty dict (不存在的配置文件返回空字典)."""
    d = load_config_file(Path("/nonexistent/md-mid.yaml"))
    assert d == {}


def test_load_config_file_flat_keys(tmp_path: Path) -> None:
    """Flat key config (扁平键配置)."""
    cfg_file = tmp_path / "md-mid.yaml"
    cfg_file.write_text("default-target: markdown\n")
    d = load_config_file(cfg_file)
    assert d["target"] == "markdown"


def test_load_config_file_invalid_yaml(tmp_path: Path) -> None:
    """Invalid YAML returns empty dict with no crash (无效 YAML 不崩溃)."""
    cfg_file = tmp_path / "md-mid.yaml"
    cfg_file.write_text(": invalid: yaml: {{{\n")
    d = load_config_file(cfg_file)
    assert d == {}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_load_config_file -v`
Expected: FAIL with `ImportError`

**Step 3: Write minimal implementation**

Add to `src/md_mid/config.py`:

```python
import logging
from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML(typ="safe")
_log = logging.getLogger(__name__)


def load_config_file(path: Path) -> dict[str, object]:
    """Load config from YAML file, return flat dict (从 YAML 文件加载配置，返回扁平字典).

    Supports the nested structure from PRD SS10.2:
    ```yaml
    default-target: latex
    latex:
      mode: full
      code-style: lstlisting
    markdown:
      locale: zh
    ```

    Note: When 'latex' and 'markdown' sections share a key name, later section wins.
    This is unlikely in practice since latex/markdown options are disjoint by design.
    (注意：latex 和 markdown 段的同名键后者覆盖前者，实际中不太可能因为选项不重叠。)

    Args:
        path: Path to config file (配置文件路径)

    Returns:
        Flat dict with only explicitly-set keys (仅含显式设置键的扁平字典)
    """
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            data = _yaml.load(f)
    except Exception:
        _log.warning("Failed to parse config file: %s", path)
        return {}

    if not isinstance(data, dict):
        return {}

    # Flatten nested sections into single dict (展平嵌套段为单层字典)
    flat: dict[str, object] = {}

    for key, val in data.items():
        if key == "default-target":
            # Special top-level key (特殊顶层键映射)
            flat["target"] = val
        elif isinstance(val, dict):
            # Nested section like "latex:" or "markdown:" (嵌套段)
            for sub_key, sub_val in val.items():
                flat[sub_key] = sub_val
        else:
            flat[key] = val

    return flat
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/md_mid/config.py tests/test_config.py
git commit -m "feat(config): add external config file loader (md-mid.yaml)"
```

---

## Task 3: Template System

**Files:**
- Modify: `src/md_mid/config.py` -- Add `load_template()`
- Create: `templates/ieee.yaml` -- Example template
- Test: `tests/test_config.py` -- Template loading tests

Templates are a subset of config focused on LaTeX preamble: `documentclass`, `classoptions`, `packages`, `package-options`, `extra-preamble`, `bibstyle`.

**Step 1: Write the failing test**

```python
from md_mid.config import load_template


def test_load_template(tmp_path: Path) -> None:
    """Load LaTeX template (加载 LaTeX 模板)."""
    tpl = tmp_path / "ieee.yaml"
    tpl.write_text(
        "documentclass: IEEEtran\n"
        "classoptions: [conference]\n"
        "packages:\n"
        "  - amsmath\n"
        "  - graphicx\n"
        "  - cite\n"
        "bibstyle: IEEEtran\n"
        "extra-preamble: |\n"
        "  \\IEEEoverridecommandlockouts\n"
    )
    d = load_template(tpl)
    assert d["documentclass"] == "IEEEtran"
    assert d["classoptions"] == ["conference"]
    assert "cite" in d["packages"]
    assert d["bibstyle"] == "IEEEtran"
    assert d["preamble"] == "\\IEEEoverridecommandlockouts\n"


def test_load_template_not_found() -> None:
    """Missing template returns empty dict (不存在的模板返回空字典)."""
    d = load_template(Path("/nonexistent/template.yaml"))
    assert d == {}


def test_load_template_invalid_yaml(tmp_path: Path) -> None:
    """Invalid YAML in template returns empty dict (模板中无效 YAML 不崩溃)."""
    tpl = tmp_path / "bad.yaml"
    tpl.write_text(": bad {{{\n")
    d = load_template(tpl)
    assert d == {}
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_config.py::test_load_template -v`

**Step 3: Implement**

Add to `src/md_mid/config.py`:

```python
def load_template(path: Path) -> dict[str, object]:
    """Load LaTeX template from YAML file, return dict (从 YAML 文件加载模板).

    Template keys are a subset of config (PRD SS10.3):
    documentclass, classoptions, packages, package-options, extra-preamble, bibstyle.

    The key 'extra-preamble' is mapped to 'preamble' for MdMidConfig compatibility.
    (extra-preamble 映射为 preamble 以兼容 MdMidConfig。)

    Args:
        path: Path to template file (模板文件路径)

    Returns:
        Dict with only explicitly-set template keys (仅含显式设置键的字典)
    """
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            data = _yaml.load(f)
    except Exception:
        _log.warning("Failed to parse template file: %s", path)
        return {}

    if not isinstance(data, dict):
        return {}

    # Map template-specific keys to config keys (映射模板键到配置键)
    if "extra-preamble" in data:
        data["preamble"] = data.pop("extra-preamble")

    return dict(data)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`

**Step 5: Create example template and commit**

Create `templates/ieee.yaml`:

```yaml
documentclass: IEEEtran
classoptions: [conference]
packages:
  - amsmath
  - graphicx
  - cite
extra-preamble: |
  \IEEEoverridecommandlockouts
bibstyle: IEEEtran
```

```bash
git add src/md_mid/config.py tests/test_config.py templates/ieee.yaml
git commit -m "feat(config): add LaTeX template loader and example IEEE template"
```

---

## Task 4: CLI Integration -- Config Resolution Pipeline

**Files:**
- Modify: `src/md_mid/cli.py` -- Add `--template`, `--config`, `--bibliography-mode`; wire up config pipeline
- Modify: `tests/test_cli.py` -- CLI config tests

This is the key integration task. The CLI:
1. Collects options, all defaulting to `None` (not their real defaults)
2. Loads template and config file into dicts
3. Calls `resolve_config()` with all layers
4. Passes resolved values as **individual kwargs** to renderers (not a config object)

**Design rationale (from code review):** Click always passes default values for options.
If CLI options default to `"full"`, `"zh"`, etc., they would always appear in the CLI
override dict and clobber template/config values. By defaulting to `None` and filtering,
only explicitly-provided CLI args participate in the override layer.

Renderers keep their individual keyword params (not a `config=` object) to maintain
backward compatibility with existing tests that call `LaTeXRenderer(mode="body")`.

**Step 1: Write the failing test**

In `tests/test_cli.py`:

```python
from pathlib import Path

from click.testing import CliRunner

from md_mid.cli import main


def test_cli_template_option(tmp_path: Path) -> None:
    """--template loads LaTeX template (--template 加载 LaTeX 模板)."""
    tpl = tmp_path / "my.yaml"
    tpl.write_text("documentclass: IEEEtran\nclassoptions: [conference]\n")
    src = tmp_path / "t.mid.md"
    src.write_text("# Hello\n\nWorld.\n")
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--template", str(tpl)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\documentclass[conference]{IEEEtran}" in content


def test_cli_config_option(tmp_path: Path) -> None:
    """--config loads external config (--config 加载外部配置)."""
    cfg = tmp_path / "md-mid.yaml"
    cfg.write_text("latex:\n  thematic-break: hrule\n")
    src = tmp_path / "t.mid.md"
    src.write_text("---\n\n")
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--config", str(cfg)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\hrule" in content


def test_cli_bibliography_mode_none(tmp_path: Path) -> None:
    """--bibliography-mode none suppresses bibliography (隐藏参考文献)."""
    src = tmp_path / "t.mid.md"
    src.write_text("<!-- bibliography: refs.bib -->\n\n# Intro\n\nText.\n")
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--bibliography-mode", "none"]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\bibliography" not in content


def test_cli_explicit_mode_overrides_config(tmp_path: Path) -> None:
    """CLI --mode overrides config file mode (CLI 覆盖配置文件)."""
    cfg = tmp_path / "md-mid.yaml"
    cfg.write_text("latex:\n  mode: body\n")
    src = tmp_path / "t.mid.md"
    src.write_text("# Intro\n\nText.\n")
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main, [str(src), "-o", str(out), "--config", str(cfg), "--mode", "full"]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "\\documentclass" in content  # full mode has preamble (full 模式有前言)
```

**Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_cli.py::test_cli_template_option -v`
Expected: FAIL -- `--template` option not recognized.

**Step 3: Implement**

In `src/md_mid/cli.py`, add new options with `default=None`:

```python
@click.option("--template", "template_path", type=click.Path(exists=True, path_type=Path), default=None,
              help="LaTeX template file (.yaml)")
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None,
              help="External config file (md-mid.yaml)")
@click.option("--bibliography-mode", type=click.Choice(["auto", "standalone", "external", "none"]),
              default=None, help="Bibliography output strategy")
```

**CRITICAL:** Change existing Click options to default to `None`:

```python
# Before (BROKEN: Click always passes "full", clobbering config/template)
@click.option("--mode", type=click.Choice(["full", "body", "fragment"]), default="full")
@click.option("--locale", type=click.Choice(["zh", "en"]), default="zh")
@click.option("--heading-id-style", type=click.Choice(["attr", "html"]), default="attr")

# After (CORRECT: None = not set by CLI, handled by resolve_config)
@click.option("--mode", type=click.Choice(["full", "body", "fragment"]), default=None)
@click.option("--locale", type=click.Choice(["zh", "en"]), default=None)
@click.option("--heading-id-style", type=click.Choice(["attr", "html"]), default=None)
```

In `main()`, after `process_comments()`, build config:

```python
from md_mid.config import load_config_file, load_template, resolve_config

# Build CLI override dict — only non-None values (仅非 None 值参与覆盖)
cli_dict: dict[str, object] = {}
if mode is not None:
    cli_dict["mode"] = mode
if locale is not None:
    cli_dict["locale"] = locale
if heading_id_style is not None:
    cli_dict["heading_id_style"] = heading_id_style
if bibliography_mode is not None:
    cli_dict["bibliography_mode"] = bibliography_mode

# Load config layers (加载配置层)
template_dict = load_template(Path(template_path)) if template_path else None
config_dict = load_config_file(Path(config_path)) if config_path else None

# Resolve final config (解析最终配置)
cfg = resolve_config(
    cli_overrides=cli_dict,
    east_meta=east.metadata,
    config_dict=config_dict,
    template_dict=template_dict,
)

# Pass resolved values to renderers as individual kwargs (将值作为独立参数传递)
if target == "latex":
    renderer = LaTeXRenderer(
        mode=cfg.mode,
        ref_tilde=cfg.ref_tilde,
        code_style=cfg.code_style,
        thematic_break=cfg.thematic_break,
        locale=cfg.locale,
        diag=diag,
    )
    # Inject resolved metadata back into EAST for preamble generation
    # (将解析后的元数据回注入 EAST 用于前言生成)
    east.metadata.update({
        "documentclass": cfg.documentclass,
        "classoptions": cfg.classoptions,
        "packages": cfg.packages,
        "package_options": cfg.package_options,
        "bibliography": cfg.bibliography,
        "bibstyle": cfg.bibstyle,
        "preamble": cfg.preamble,
    })
elif target == "markdown":
    renderer = MarkdownRenderer(
        bib=bib_data,
        heading_id_style=cfg.heading_id_style,
        locale=cfg.locale,
        mode=cfg.mode,
        diag=diag,
    )
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_cli.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/config.py src/md_mid/cli.py tests/test_cli.py
git commit -m "feat(config,cli): wire up config resolution with --template, --config, --bibliography-mode"
```

---

## Task 5: Code Block Style -- lstlisting vs minted

**Files:**
- Modify: `src/md_mid/latex.py` -- Read `code_style` param in `render_code_block()`
- Modify: `tests/test_latex.py` -- Test minted output

**Note:** The `minted` package requires `\usepackage{minted}` in the preamble AND the
`-shell-escape` flag when compiling. Users must ensure their template/config includes
`minted` in the packages list. The code block style config does NOT auto-add the package
import — that is the template/config's responsibility, keeping concerns separated.

**Step 1: Write the failing test**

```python
def test_code_block_minted(self):
    """minted code block rendering (minted 代码块渲染)."""
    c = CodeBlock(content="x = 1", language="python")
    result = render(c, code_style="minted")
    assert "\\begin{minted}{python}" in result
    assert "x = 1" in result
    assert "\\end{minted}" in result


def test_code_block_minted_no_lang(self):
    """minted code block without language falls back to verbatim (minted 无语言回退)."""
    c = CodeBlock(content="hello", language="")
    result = render(c, code_style="minted")
    assert "\\begin{verbatim}" in result


def test_code_block_lstlisting_default(self):
    """Default lstlisting code block unchanged (默认 lstlisting 不变)."""
    c = CodeBlock(content="x = 1", language="python")
    result = render(c)
    assert "\\begin{lstlisting}" in result
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

In `src/md_mid/latex.py`, add `code_style` and `thematic_break` params to `__init__`:

```python
def __init__(
    self,
    mode: str = "full",
    ref_tilde: bool = True,
    code_style: str = "lstlisting",
    thematic_break: str = "newpage",
    diag: DiagCollector | None = None,
) -> None:
    ...
    self.code_style = code_style
    self.thematic_break_style = thematic_break
```

Update `render_code_block()`:

```python
def render_code_block(self, node: Node) -> str:
    cb = cast(CodeBlock, node)
    if self.code_style == "minted":
        if cb.language:
            return (
                f"\\begin{{minted}}{{{cb.language}}}\n"
                f"{cb.content}\n"
                f"\\end{{minted}}\n"
            )
        # No language: fall back to verbatim (无语言：回退到 verbatim)
        return f"\\begin{{verbatim}}\n{cb.content}\n\\end{{verbatim}}\n"
    # Default: lstlisting (默认：lstlisting)
    if cb.language:
        return (
            f"\\begin{{lstlisting}}[language={cb.language}]\n"
            f"{cb.content}\n"
            f"\\end{{lstlisting}}\n"
        )
    return f"\\begin{{lstlisting}}\n{cb.content}\n\\end{{lstlisting}}\n"
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): configurable code block style (lstlisting/minted)"
```

---

## Task 6: Thematic Break Style -- newpage / hrule / ignore

**Files:**
- Modify: `src/md_mid/latex.py` -- Read `thematic_break_style` in `render_thematic_break()`
- Modify: `tests/test_latex.py` -- Test hrule and ignore

**Step 1: Write the failing test**

```python
def test_thematic_break_hrule(self):
    """hrule thematic break (hrule 分隔线)."""
    result = render(ThematicBreak(), thematic_break="hrule")
    assert "\\hrule" in result
    assert "\\newpage" not in result


def test_thematic_break_ignore(self):
    """ignore thematic break produces empty (ignore 分隔线为空)."""
    result = render(ThematicBreak(), thematic_break="ignore")
    assert result.strip() == ""


def test_thematic_break_default_newpage(self):
    """Default newpage thematic break (默认 newpage)."""
    result = render(ThematicBreak())
    assert "\\newpage" in result
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

```python
def render_thematic_break(self, node: Node) -> str:
    if self.thematic_break_style == "hrule":
        return "\\hrule\n"
    if self.thematic_break_style == "ignore":
        return ""
    return "\\newpage\n"
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): configurable thematic break (newpage/hrule/ignore)"
```

---

## Task 7: `include-tex` Directive

**Files:**
- Modify: `src/md_mid/comment.py` -- Handle `include-tex` directive
- Modify: `tests/test_comment.py` -- Tests for include-tex

The `include-tex` directive reads an external `.tex` file and inserts its content as a
`RawBlock` node, replacing the directive comment.

**Security considerations (from code review):**
1. **Path traversal prevention:** The resolved include path must stay under the source
   file's directory (or project root). Paths like `../../../etc/passwd` must be rejected.
2. **No `.strip()`:** TeX content is inserted verbatim — `strip()` could break TeX
   fragments that depend on leading/trailing whitespace or newlines.
3. **Recursion depth limit:** Included files could themselves contain `include-tex`
   directives. We do NOT process includes recursively (includes are one-level only).
   If recursive includes are needed later, add a depth limit.

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_include_tex_creates_raw_block(tmp_path: Path) -> None:
    """include-tex creates RawBlock from file (include-tex 创建 RawBlock)."""
    tex_file = tmp_path / "frag.tex"
    tex_file.write_text("\\begin{equation}\nx^2\n\\end{equation}\n")
    src_file = tmp_path / "t.mid.md"
    md_text = f"# Intro\n\n<!-- include-tex: frag.tex -->\n\nMore text.\n"
    doc = parse(md_text)
    east = process_comments(doc, str(src_file), diag=DiagCollector(str(src_file)))
    raws = [c for c in east.children if isinstance(c, RawBlock)]
    assert len(raws) == 1
    assert "\\begin{equation}" in raws[0].content


def test_include_tex_relative_path(tmp_path: Path) -> None:
    """include-tex resolves relative path (include-tex 相对路径解析)."""
    sub = tmp_path / "tables"
    sub.mkdir()
    tex = sub / "complex.tex"
    tex.write_text("\\begin{tabular}{ll}\nA & B\n\\end{tabular}\n")
    src = tmp_path / "paper.mid.md"
    md = "# Tables\n\n<!-- include-tex: tables/complex.tex -->\n"
    doc = parse(md)
    east = process_comments(doc, str(src), diag=DiagCollector(str(src)))
    raws = [c for c in east.children if isinstance(c, RawBlock)]
    assert len(raws) == 1
    assert "tabular" in raws[0].content


def test_include_tex_file_not_found(tmp_path: Path) -> None:
    """Missing include file triggers error (文件不存在触发错误)."""
    src = tmp_path / "t.mid.md"
    md = "# Intro\n\n<!-- include-tex: nonexistent.tex -->\n"
    doc = parse(md)
    dc = DiagCollector(str(src))
    process_comments(doc, str(src), diag=dc)
    assert dc.has_errors
    assert any("not found" in d.message.lower() for d in dc.errors)


def test_include_tex_path_traversal_rejected(tmp_path: Path) -> None:
    """Path traversal in include-tex is rejected (路径遍历被拒绝)."""
    # Create a file outside source dir (在源目录外创建文件)
    outer = tmp_path / "outer"
    outer.mkdir()
    secret = outer / "secret.tex"
    secret.write_text("SECRET CONTENT")
    # Source file is in a subdirectory (源文件在子目录中)
    inner = tmp_path / "inner"
    inner.mkdir()
    src = inner / "paper.mid.md"
    md = "<!-- include-tex: ../outer/secret.tex -->\n"
    doc = parse(md)
    dc = DiagCollector(str(src))
    process_comments(doc, str(src), diag=dc)
    assert dc.has_errors
    assert any("traversal" in d.message.lower() or "outside" in d.message.lower()
               for d in dc.errors)


def test_include_tex_preserves_content_verbatim(tmp_path: Path) -> None:
    """include-tex preserves content verbatim, no strip (内容原样保留)."""
    tex = tmp_path / "frag.tex"
    # Leading/trailing whitespace matters in TeX (TeX 中前后空白有意义)
    tex.write_text("\n  \\command\n\n")
    src = tmp_path / "t.mid.md"
    doc = parse("<!-- include-tex: frag.tex -->\n")
    east = process_comments(doc, str(src), diag=DiagCollector(str(src)))
    raws = [c for c in east.children if isinstance(c, RawBlock)]
    assert len(raws) == 1
    assert raws[0].content == "\n  \\command\n\n"
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

In `src/md_mid/comment.py`, add `include-tex` to known directives:

```python
_ALL_KNOWN_DIRECTIVES = DOCUMENT_DIRECTIVES | ATTACH_UP_DIRECTIVES | frozenset({"begin", "end", "include-tex"})
```

Add a new phase that handles `include-tex`:

```python
def _process_includes(
    children: list[Node],
    source_dir: Path,
    diag: DiagCollector,
) -> None:
    """Process include-tex directives, replacing with RawBlock (处理 include-tex 指令).

    Includes are one-level only — included content is not scanned for further
    include-tex directives. This prevents circular inclusion.
    (引入为单层 — 引入的内容不再扫描 include-tex，防止循环引入。)

    Args:
        children: Node list to scan (待扫描的节点列表)
        source_dir: Directory of source file for relative path resolution (源文件目录)
        diag: Diagnostic collector (诊断收集器)
    """
    i = 0
    while i < len(children):
        child = children[i]
        parsed = _parse_comment(child)
        if parsed is not None:
            key, value = parsed
            if key == "include-tex":
                tex_rel = str(value).strip()
                tex_path = (source_dir / tex_rel).resolve()
                # Security: path traversal check (安全：路径遍历检查)
                try:
                    tex_path.relative_to(source_dir.resolve())
                except ValueError:
                    diag.error(
                        f"include-tex path traversal outside source directory: {tex_rel}",
                        _pos_from_node(child),
                    )
                    i += 1
                    continue
                if not tex_path.exists():
                    diag.error(
                        f"include-tex file not found: {tex_rel}",
                        _pos_from_node(child),
                    )
                    i += 1
                    continue
                # Read verbatim — no strip() (原样读取 — 不去空白)
                content = tex_path.read_text(encoding="utf-8")
                children[i] = RawBlock(content=content, position=child.position)
                i += 1
                continue
        i += 1
```

Update `process_comments()` to call `_process_includes`:

```python
def process_comments(doc, filename, *, diag=None):
    if diag is None:
        diag = DiagCollector(filename)

    source_dir = Path(filename).parent if filename != "<stdin>" else Path(".")

    _collect_document_directives(doc, diag)
    _process_environments(doc, diag)
    _process_includes(doc.children, source_dir, diag)  # NEW (新增)
    _process_attachments(doc, diag)

    return doc
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_comment.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/comment.py tests/test_comment.py
git commit -m "feat(comment): add include-tex directive with path traversal protection"
```

---

## Task 8: Environment `args` as YAML Sequence

**Files:**
- Modify: `src/md_mid/latex.py` -- Handle list-type `args`
- Modify: `tests/test_latex.py` -- Test list args rendering

PRD SS11 says `args` renders as `{arg1}{arg2}` when the value is a YAML sequence,
and `options` renders as `[opt]`. Currently, `args` is treated as a single string.

**Step 1: Write the failing test**

```python
def test_environment_args_list(self):
    """Environment args as list renders {arg1} (环境列表参数渲染)."""
    env = Environment(
        name="subfigure",
        children=[Paragraph(children=[Text(content="content")])],
    )
    env.metadata["args"] = [r"0.45\textwidth"]
    result = render(env)
    assert r"\begin{subfigure}{0.45\textwidth}" in result


def test_environment_args_multiple(self):
    """Multiple args render as consecutive braces (多参数渲染为连续花括号)."""
    env = Environment(
        name="myenv",
        children=[Paragraph(children=[Text(content="text")])],
    )
    env.metadata["args"] = ["arg1", "arg2"]
    result = render(env)
    assert r"\begin{myenv}{arg1}{arg2}" in result


def test_environment_args_string_unchanged(self):
    """String args still works as before (字符串参数不变)."""
    env = Environment(
        name="test",
        children=[Paragraph(children=[Text(content="body")])],
    )
    env.metadata["args"] = "single"
    result = render(env)
    assert r"\begin{test}{single}" in result


def test_environment_options_and_args_combined(self):
    """Options and args render together: [opt]{arg} (选项和参数组合渲染)."""
    env = Environment(
        name="minipage",
        children=[Paragraph(children=[Text(content="text")])],
    )
    env.metadata["options"] = "c"
    env.metadata["args"] = [r"0.5\textwidth"]
    result = render(env)
    assert r"\begin{minipage}[c]{0.5\textwidth}" in result
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

In `src/md_mid/latex.py`, update `render_environment()`:

```python
def render_environment(self, node: Node) -> str:
    env = cast(Environment, node)
    name = env.name
    meta = node.metadata
    opts = meta.get("options", "")
    args = meta.get("args", "")

    header = f"\\begin{{{name}}}"
    if opts:
        header += f"[{opts}]"
    # Handle args as list or string (处理列表或字符串参数)
    if isinstance(args, list):
        for arg in args:
            header += f"{{{arg}}}"
    elif args:
        header += f"{{{args}}}"

    content = self.render_children(node)

    if label := meta.get("label"):
        return f"{header}\n\\label{{{label}}}\n{content}\\end{{{name}}}\n"

    return f"{header}\n{content}\\end{{{name}}}\n"
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): support YAML list args for environment rendering"
```

---

## Task 9: LaTeX Footnote Two-Pass Rendering

**Files:**
- Modify: `src/md_mid/latex.py` -- Add footnote collection in `render_document()`, expand at ref sites
- Modify: `tests/test_latex.py` -- Footnote rendering tests

Currently `render_footnote_ref` outputs `\footnotemark[ref_id]` using markdown-it-py's
internal 0-based ID, which is incorrect for LaTeX. PRD SS5.3 says: collect `FootnoteDef`
in Pass 1, then at each `FootnoteRef` site, expand as `\footnote{content}`.

**Design rationale (from code review):** The pre-scan MUST happen in `render_document()`
(called once for the root Document node), NOT in `render()` (the recursive dispatch
method called for every node). Placing it in `render()` would cause O(n^2) re-scanning
on every node visit. The `_fn_defs` dict is initialized in `__init__` to avoid lifecycle
issues.

**Step 1: Write the failing test**

```python
from md_mid.nodes import FootnoteRef, FootnoteDef


class TestLatexFootnotes:
    def test_footnote_expands_inline(self):
        """Footnote expands at reference site (脚注在引用处展开)."""
        fn_def = FootnoteDef(
            def_id="0",
            children=[Paragraph(children=[Text(content="My note")])],
        )
        p = Paragraph(children=[
            Text(content="See this"),
            FootnoteRef(ref_id="0"),
            Text(content=" and more."),
        ])
        doc = Document(children=[p, fn_def])
        result = render(doc)
        assert "\\footnote{My note}" in result
        # FootnoteDef itself should not appear in output (脚注定义不出现在输出中)
        assert "\\footnotetext" not in result

    def test_footnote_unknown_ref_fallback(self):
        """Unknown footnote ref falls back gracefully (未知脚注引用回退)."""
        p = Paragraph(children=[
            Text(content="See this"),
            FootnoteRef(ref_id="999"),
        ])
        doc = Document(children=[p])
        result = render(doc)
        # No crash, produces some footnote marker (不崩溃，产出某种脚注标记)
        assert "\\footnote" in result

    def test_footnote_multiple_refs(self):
        """Multiple footnotes each expand correctly (多个脚注各自正确展开)."""
        fn1 = FootnoteDef(def_id="0", children=[Paragraph(children=[Text(content="Note A")])])
        fn2 = FootnoteDef(def_id="1", children=[Paragraph(children=[Text(content="Note B")])])
        p = Paragraph(children=[
            Text(content="First"),
            FootnoteRef(ref_id="0"),
            Text(content=" second"),
            FootnoteRef(ref_id="1"),
        ])
        doc = Document(children=[p, fn1, fn2])
        result = render(doc)
        assert "\\footnote{Note A}" in result
        assert "\\footnote{Note B}" in result
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

In `src/md_mid/latex.py`:

1. Add `_fn_defs` dict to `__init__`:

```python
def __init__(self, ...) -> None:
    ...
    self._fn_defs: dict[str, Node] = {}  # footnote defs by id (按 ID 索引的脚注定义)
```

2. Add pre-scan in `render_document()` (NOT in `render()`):

```python
def render_document(self, node: Node) -> str:
    # Pre-scan: collect all FootnoteDef nodes (预扫描：收集所有脚注定义)
    self._collect_footnote_defs(node)

    meta = node.metadata
    if self.mode == "full":
        ...  # existing preamble logic
    ...  # rest of existing render_document logic


def _collect_footnote_defs(self, node: Node) -> None:
    """Pre-scan tree to collect FootnoteDef nodes by id (预扫描收集脚注定义).

    Called once from render_document(), not from render().
    """
    if isinstance(node, FootnoteDef):
        self._fn_defs[node.def_id] = node
    for child in node.children:
        self._collect_footnote_defs(child)
```

3. Update `render_footnote_ref` to expand inline:

```python
def render_footnote_ref(self, node: Node) -> str:
    """Expand footnote inline at reference site (在引用处展开脚注)."""
    fr = cast(FootnoteRef, node)
    fn_def = self._fn_defs.get(fr.ref_id)
    if fn_def is not None:
        content = self.render_children(fn_def).strip()
        return f"\\footnote{{{content}}}"
    # Fallback: unknown ref — emit mark (回退：未知引用)
    return f"\\footnote{{[{fr.ref_id}]}}"
```

4. Update `render_footnote_def` to skip (content already expanded at ref):

```python
def render_footnote_def(self, node: Node) -> str:
    """Skip — content already expanded at FootnoteRef site (跳过 — 内容已在引用处展开)."""
    return ""
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): two-pass footnote rendering with inline expansion"
```

---

## Task 10: LaTeX Locale Support

**Files:**
- Modify: `src/md_mid/latex.py` -- Add locale-aware preamble commands
- Modify: `tests/test_latex.py` -- Locale tests

When `locale=en`, inject `\renewcommand{\figurename}{Figure}` and `\tablename` into
the preamble. For Chinese (`zh`), these are typically handled by the `ctex` package
which most Chinese LaTeX documents already use. If ctex is detected in the packages list,
no override is needed. If ctex is NOT in the packages list and locale is `zh`, we do NOT
auto-add ctex (that would be overreach) — the user handles their own CJK setup.

**Step 1: Write the failing test**

```python
def test_latex_locale_english_figurename(self):
    """English locale sets figurename (英文 locale 设置 figurename)."""
    doc = Document(children=[Figure(src="a.png", alt="")])
    doc.metadata["title"] = "Paper"
    result = render(doc, mode="full", locale="en")
    assert "\\renewcommand{\\figurename}{Figure}" in result
    assert "\\renewcommand{\\tablename}{Table}" in result


def test_latex_locale_zh_no_override(self):
    """Chinese locale does not add figurename (中文 locale 不额外设置)."""
    doc = Document(children=[])
    doc.metadata["title"] = "Paper"
    result = render(doc, mode="full", locale="zh")
    assert "\\figurename" not in result
```

**Step 2: Run tests, expect failures**

**Step 3: Implement**

Add `locale` param to `LaTeXRenderer.__init__`:

```python
def __init__(self, ..., locale: str = "zh", ...) -> None:
    ...
    self.locale = locale
```

In `render_document`, after packages but before title, conditionally inject:

```python
# Locale-specific preamble (本地化前言)
if self.locale == "en":
    lines.append("\\renewcommand{\\figurename}{Figure}")
    lines.append("\\renewcommand{\\tablename}{Table}")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_latex.py -v && make check`

**Step 5: Commit**

```bash
git add src/md_mid/latex.py tests/test_latex.py
git commit -m "feat(latex): add locale support for figure/table names in preamble"
```

---

## Execution Order

```
Task 1 (Config dataclass + resolve) --> Task 2 (Config file) --> Task 3 (Template) --> Task 4 (CLI)
                                                                                         |
                                                                                Tasks 5, 6, 10
Task 7 (include-tex)  -- independent
Task 8 (Env args)     -- independent
Task 9 (Footnotes)    -- independent
```

**Recommended order:** 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10

Tasks 7-9 can be parallelized after Task 1 if desired. Tasks 5, 6, 10 depend on Task 4.

---

## Verification

After all tasks:

```bash
make check   # ruff 0, mypy 0, all tests green
```

Manual spot-checks:

1. `md-mid paper.md --template templates/ieee.yaml -o paper.tex` -> uses IEEEtran documentclass
2. `md-mid paper.md --config md-mid.yaml -o paper.tex` -> config values applied
3. `md-mid paper.md --bibliography-mode none -o paper.tex` -> no `\bibliography` in output
4. Code block with `language=python` + config `code-style: minted` -> `\begin{minted}{python}`
5. `---` with config `thematic-break: hrule` -> `\hrule` instead of `\newpage`
6. `<!-- include-tex: tables/complex.tex -->` -> `.tex` content inserted as raw block
7. `<!-- args: [0.45\textwidth] -->` on subfigure -> `\begin{subfigure}{0.45\textwidth}`
8. `[^note]` + `[^note]: text` -> `\footnote{text}` in LaTeX output
9. `--locale en` -> `\renewcommand{\figurename}{Figure}` in preamble

---

## Changes from Review Feedback

This plan incorporates feedback from three independent model reviews:

| Issue | Source | Fix |
|-------|--------|-----|
| `merge()` comparing to defaults is broken | Review 1, 2 | Dict-based layered merge (Task 1) |
| Click always passes default values | Review 1, 2 | CLI options default to `None` (Task 4) |
| `LaTeXRenderer(config=cfg)` breaks tests | Review 1 | Keep individual kwargs (Task 4) |
| `_render_node()` doesn't exist in Task 9 | Review 1 | Use existing `render()` dispatch (Task 9) |
| Pre-scan in `render()` causes O(n^2) | Review 1, 3 | Pre-scan in `render_document()` (Task 9) |
| `include-tex` needs path traversal check | Review 1 | `resolve().relative_to()` check (Task 7) |
| `include-tex` `.strip()` breaks TeX | Review 1 | Read verbatim, no strip (Task 7) |
| Task 8 minipage test uses wrong syntax | Review 2 | Use subfigure + combined options test (Task 8) |
| minted needs `\usepackage{minted}` note | Review 1 | Added note in Task 5 |
| YAML parse error handling | Review 2 | try/except in Tasks 2, 3 |
| List merge strategy unclear | Review 3 | Documented: replace, not append (Task 1) |
| `_fn_defs` lifecycle in recursive render | Review 3 | Init in `__init__`, scan in `render_document` (Task 9) |
| ctex auto-detection for Chinese locale | Review 3 | Documented: no auto-add (Task 10) |

---

## Post-Execution Checklist

- [ ] **PRD SS10**: Verify config file format matches implementation
- [ ] **PRD SS9**: CLI help updated with new options
- [ ] **PRD SS4.2.2**: `include-tex` behavior documented
- [ ] **PRD SS7.1**: `render_code_block` note about minted support
- [ ] **PRD SS5.3**: Footnote rendering strategy documented as two-pass inline expansion
- [ ] **Security**: `include-tex` path traversal test passes
- [ ] **Backward compat**: Existing tests still pass with no changes
