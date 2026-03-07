# Placement Directives Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add consistent `<!-- placement: ... -->` support for Markdown figures and tables, with documentation, validation, and regression tests.

**Architecture:** Reuse the existing attach-up metadata path instead of inventing new Markdown syntax. Keep `placement` as a structured metadata field, ensure figures and tables both document and preserve it, and add lightweight validation so malformed float strings are visible without breaking the pipeline.

**Tech Stack:** Python 3.14, dataclass-based AST, regex-based comment parsing, pytest, uv, Makefile

---

## Task 1: Document `placement` for both figures and tables

**Files:**
- Modify: `docs/wenqiao-format-spec.md`

**Step 1: Write the failing doc expectation**

Check the current table section and confirm it has no documented `placement` example.

**Step 2: Update the figure section**

Add a figure example that includes:

```markdown
<!-- placement: h -->
```

Clarify that `placement` is LaTeX-only metadata and defaults to `htbp`.

**Step 3: Update the table section**

Add the same directive to the table example and add a short directive table for table attach-up metadata:

- `caption`
- `label`
- `placement`

**Step 4: Review wording for consistency**

Make sure figure/table sections describe the same semantics:

- explicit attach-up directive
- LaTeX-only effect
- default `htbp`

**Step 5: Commit**

```bash
git add docs/wenqiao-format-spec.md
git commit -m "docs: specify placement directives for figures and tables"
```

---

## Task 2: Add attachment tests for `placement`

**Files:**
- Modify: `tests/test_comment.py`

**Step 1: Write the failing tests**

Add tests covering:

```python
def test_placement_attaches_to_image() -> None:
    ...

def test_placement_attaches_to_table() -> None:
    ...
```

Assertions should verify that processed nodes carry `metadata["placement"] == "h"`.

**Step 2: Run tests to verify current behavior**

Run: `uv run pytest tests/test_comment.py -v`

Expected:
- Either the new table test fails because attachment is incomplete for tables in practice
- Or both pass, which proves implementation already exists and the task becomes regression-only

**Step 3: Adjust minimal implementation if needed**

If tests reveal a gap, update `src/wenqiao/comment.py` so `placement` is attached through the same path as `caption` and `label`.

**Step 4: Run tests again**

Run: `uv run pytest tests/test_comment.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_comment.py src/wenqiao/comment.py
git commit -m "test: cover placement attachment for figures and tables"
```

---

## Task 3: Add LaTeX rendering coverage for table placement

**Files:**
- Modify: `tests/test_latex.py`
- Modify: `src/wenqiao/latex_blocks.py` (only if test exposes a real gap)

**Step 1: Write the failing test**

Add:

```python
def test_table_custom_placement(self) -> None:
    t = Table(headers=_cells("A"), alignments=["left"], rows=_rows(["1"]))
    t.metadata["placement"] = "h"
    result = render(t)
    assert "\\begin{table}[h]" in result
```

**Step 2: Run the targeted test**

Run: `uv run pytest tests/test_latex.py::TestTable::test_table_custom_placement -v`

Expected:
- PASS if support already exists
- FAIL only if renderer still ignores table placement

**Step 3: Implement minimal fix if needed**

Ensure `render_table()` reads `metadata["placement"]` and defaults to `htbp` when absent.

**Step 4: Re-run the targeted tests**

Run:

```bash
uv run pytest \
  tests/test_latex.py::TestFigure::test_figure_custom_placement \
  tests/test_latex.py::TestTable::test_table_custom_placement -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_latex.py src/wenqiao/latex_blocks.py
git commit -m "test: cover custom table placement rendering"
```

---

## Task 4: Add validation for malformed placement values

**Files:**
- Modify: `src/wenqiao/validate.py`
- Modify: `tests/test_validate.py`

**Step 1: Write the failing tests**

Add tests such as:

```python
def test_validate_valid_placement_has_no_warning() -> None:
    ...

def test_validate_invalid_placement_warns() -> None:
    ...
```

Use one valid sample like `htbp` and one invalid sample like `foo?`.

**Step 2: Run targeted validation tests**

Run: `uv run pytest tests/test_validate.py -v`

Expected: FAIL for the new validation expectations

**Step 3: Implement warning-only validation**

Add a helper that:

- finds `placement` on figure/image/table nodes
- strips whitespace
- warns on empty values
- warns on characters outside an allowed float charset such as `[!htbpH]`

Do not hard-fail the document.

**Step 4: Re-run validation tests**

Run: `uv run pytest tests/test_validate.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/wenqiao/validate.py tests/test_validate.py
git commit -m "feat: validate placement directives"
```

---

## Task 5: Add end-to-end regression coverage

**Files:**
- Modify: `tests/test_e2e.py`

**Step 1: Write the failing tests**

Add an end-to-end case for:

- image + `<!-- placement: h -->`
- table + `<!-- placement: h -->`

Each test should parse source, process comments, render LaTeX, and assert custom placement appears in the generated environment header.

**Step 2: Run targeted end-to-end tests**

Run: `uv run pytest tests/test_e2e.py -v`

Expected: PASS if earlier layers are correct, otherwise FAIL with clear regression signal

**Step 3: Apply minimal fix if needed**

Only touch code if end-to-end behavior still differs from unit-level behavior.

**Step 4: Re-run targeted tests**

Run: `uv run pytest tests/test_e2e.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add end-to-end placement coverage"
```

---

## Task 6: Full verification

**Files:**
- No code changes expected

**Step 1: Run focused tests**

Run:

```bash
uv run pytest \
  tests/test_comment.py \
  tests/test_latex.py \
  tests/test_validate.py \
  tests/test_e2e.py -v --tb=short
```

Expected: PASS

**Step 2: Run full suite**

Run: `make test`

Expected: PASS

**Step 3: Run full checks**

Run: `make check`

Expected: PASS

**Step 4: Review diff**

Run:

```bash
git diff -- docs/wenqiao-format-spec.md src/wenqiao/comment.py src/wenqiao/latex_blocks.py src/wenqiao/validate.py tests/test_comment.py tests/test_latex.py tests/test_validate.py tests/test_e2e.py
```

Expected: only placement-directive related changes

**Step 5: Commit**

```bash
git add docs/wenqiao-format-spec.md src/wenqiao/comment.py src/wenqiao/latex_blocks.py src/wenqiao/validate.py tests/test_comment.py tests/test_latex.py tests/test_validate.py tests/test_e2e.py
git commit -m "feat: support placement directives for figures and tables"
```
