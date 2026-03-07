# Bare Cite/Ref Shortcuts Design

**Status:** Approved

**Goal:** Support bare bracket shortcuts `[cite:key]` and `[ref:label]` in addition to the existing Markdown link forms.

---

## Decision

Add parser-level sugar only.

- `[cite:key]` maps to `Citation(keys=["key"], display_text="")`
- `[cite:a,b,c]` maps to `Citation(keys=["a", "b", "c"], display_text="")`
- `[cite:key?cmd=citet]` maps to `Citation(..., cmd="citet")`
- `[ref:fig:x]` maps to `CrossRef(label="fig:x", display_text="fig:x")`

Existing syntax remains unchanged:

- `[text](cite:key)`
- `[text](ref:label)`

---

## Scope

- Parser support for bare shortcuts inside normal text flows
- Documentation update in format spec
- Parser and end-to-end regression tests

Out of scope:

- New renderer behavior
- New comment/directive behavior
- Attribute syntax or other shortcut families

---

## Parsing Rules

- Only recognize bracket content starting with `cite:` or `ref:`
- Preserve surrounding plain text in the same text node by splitting it
- Bare `cite:` uses empty display text
- Bare `ref:` uses the label itself as display text

---

## Rationale

- Minimal implementation surface: parser only
- No AST schema change
- Reuses current `Citation` / `CrossRef` renderers and validation path
- Keeps rich explicit link syntax for author-controlled display text
