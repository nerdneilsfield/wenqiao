# Figure/Table Placement Directives Design

**Status:** Approved

**Decision:** Use structured attach-up directives for float placement instead of introducing new Markdown syntax.

**Goal:** Let authors control LaTeX float placement for Markdown images and tables with explicit metadata comments such as `<!-- placement: h -->`.

---

## Context

The current pipeline already carries `placement` through the metadata path for figures and tables:

- Format spec documents figure-level `placement`
- Comment processing already accepts `placement` as an attach-up directive
- LaTeX rendering already emits `\begin{figure}[...]` and `\begin{table}[...]`

What is missing is a consistent author-facing contract for both figures and tables, plus validation and regression coverage.

---

## Chosen Syntax

### Figures

```markdown
![Pipeline](figures/pipeline.png)
<!-- caption: System pipeline -->
<!-- label: fig:pipeline -->
<!-- placement: h -->
```

### Tables

```markdown
| Method | RMSE |
|--------|------|
| ICP    | 2.3  |
<!-- caption: Result comparison -->
<!-- label: tab:results -->
<!-- placement: h -->
```

---

## Why This Design

### Option chosen: structured directive

Use `placement` as a first-class metadata field instead of generic `args` or a shorthand like `[h]`.

### Reasons

- It matches the existing metadata architecture.
- It keeps Markdown syntax stable.
- It is easy to ignore outside LaTeX output.
- It leaves room for future structured keys such as `width`, `height`, or table-specific controls.

### Explicit non-goals

- No `[h]` syntax sugar
- No attribute-block syntax such as `{placement=h}`
- No generic “pass arbitrary LaTeX args through Markdown” feature

---

## Data Model

`placement` remains a plain string stored in `node.metadata["placement"]`.

Affected node kinds:

- `Figure`
- `Image` promoted to figure by caption/label metadata
- `Table`

No AST schema change is required.

---

## Rendering Semantics

### LaTeX

- `Figure` uses `placement` in `\begin{figure}[<placement>]`
- `Table` uses `placement` in `\begin{table}[<placement>]`
- Default remains `htbp` when placement is absent

### Markdown/HTML

- `placement` is ignored
- Output remains unchanged for non-LaTeX targets

---

## Validation Rules

Accepted values should be conservative and LaTeX-oriented:

- Allow typical float strings such as `h`, `t`, `b`, `p`, `ht`, `htbp`, `!htbp`, `H`
- Reject empty-string values after trimming
- Warn on obviously invalid characters outside the common float alphabet

Initial implementation can be warning-based rather than hard-error based to preserve author workflow.

---

## Files Expected To Change

- `docs/wenqiao-format-spec.md`
- `src/wenqiao/comment.py`
- `src/wenqiao/latex_blocks.py`
- `tests/test_comment.py`
- `tests/test_latex.py`
- `tests/test_e2e.py`

Validation may also touch:

- `src/wenqiao/validate.py`
- `tests/test_validate.py`

---

## Test Strategy

### Comment attachment

- Figure/image attaches `placement`
- Table attaches `placement`
- Whitespace is normalized around directive values

### LaTeX rendering

- Figure renders `\begin{figure}[h]`
- Table renders `\begin{table}[h]`
- Missing placement still renders default `htbp`

### Validation

- Valid placement strings produce no diagnostics
- Invalid placement strings produce warnings

### End-to-end

- Markdown input with `<!-- placement: h -->` survives parse → comment processing → LaTeX output

---

## Risks

- If validation is too strict, it may reject legitimate LaTeX placements used by advanced users.
- If validation is too loose, malformed values may leak into generated TeX.

The recommended balance is warning-only validation over a small allowlist/character check.

---

## Follow-up

If author ergonomics later becomes a priority, `[h]` can be added as syntax sugar that normalizes into the same `placement` metadata without changing this design.
