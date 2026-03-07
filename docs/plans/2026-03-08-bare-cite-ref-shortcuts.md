# Bare Cite/Ref Shortcuts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `[cite:key]` and `[ref:label]` parser sugar while preserving the existing `[text](cite:key)` and `[text](ref:label)` behavior.

**Architecture:** Extend parser text-node handling so bare shortcuts are normalized into `Citation` and `CrossRef` nodes before rendering. Keep all renderers unchanged and verify behavior through parser and e2e tests.

**Tech Stack:** Python 3.14, markdown-it-py, pytest, uv, Makefile

---

### Task 1: Add parser tests for bare shortcuts

**Files:**
- Modify: `tests/test_parser.py`

**Step 1: Write failing tests**

Add tests for:

- bare cite
- bare ref
- bare cite with `?cmd=`
- shortcuts embedded in surrounding text

**Step 2: Run targeted tests**

Run: `uv run pytest tests/test_parser.py -v`

Expected: FAIL for the new shortcut tests

**Step 3: Implement parser support**

Update `src/wenqiao/parser.py` to split text nodes into:

- `Text`
- `Citation`
- `CrossRef`

based on bracket shortcuts.

**Step 4: Re-run targeted tests**

Run: `uv run pytest tests/test_parser.py -v`

Expected: PASS

---

### Task 2: Add end-to-end coverage

**Files:**
- Modify: `tests/test_e2e.py`

**Step 1: Write failing tests**

Add one LaTeX e2e case proving:

- `[cite:key]` becomes `\cite{key}`
- `[ref:label]` becomes `\ref{label}`

**Step 2: Run targeted tests**

Run: `uv run pytest tests/test_e2e.py -v`

Expected: FAIL before parser change, PASS after

**Step 3: Re-run after implementation**

Run: `uv run pytest tests/test_e2e.py -v`

Expected: PASS

---

### Task 3: Update docs and verify

**Files:**
- Modify: `docs/wenqiao-format-spec.md`

**Step 1: Document shorthand syntax**

Add shorthand examples in citation and cross-reference sections.

**Step 2: Run full verification**

Run:

```bash
make test
make check
```

Expected: PASS
