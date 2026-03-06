"""最小化 BibTeX 解析器：从 .bib 文件提取引用信息供 Rich Markdown 脚注使用。

Minimal BibTeX parser for extracting citation metadata for Rich
Markdown footnotes. Only extracts and formats common fields:
author, title, journal/booktitle, year.

仅支持常见字段（author, title, journal/booktitle, year）的提取与格式化。
"""

from __future__ import annotations

import re

# 匹配条目起始 @type{key, (Match entry start @type{key,)
_ENTRY_START_RE = re.compile(
    r"@(\w+)\{([^\s,{}]+)\s*,",
    re.IGNORECASE,
)

# 匹配 field = {value} 或 field = "value" 或 field = bare
# (Match field = {value}, field = "value", or field = bare)
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:"
    r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
    r"|\"([^\"]*)\""
    r"|(\S[^,\n]*))",
    re.DOTALL,
)


def _find_entry_body(text: str, start: int) -> str | None:
    """大括号平衡的条目体查找 (Find balanced-brace entry body).

    Starting after the opening ``{`` that follows the cite-key comma,
    scan forward keeping a brace depth counter and return everything
    up to the matching closing ``}``.

    从引用键逗号之后的 ``{`` 开始，向前扫描并保持大括号深度计数器，
    返回到匹配的闭合 ``}`` 之前的所有内容。

    Note: does not handle unbalanced braces inside quotes or comments.
    (注意：不处理引号或注释中的不平衡大括号。)

    Args:
        text: Full bib text (完整 bib 文本)
        start: Position right after the comma (逗号之后的位置)

    Returns:
        Body text or None if unbalanced (条目体文本，不平衡时为 None)
    """
    depth = 1
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def parse_bib(bib_text: str) -> dict[str, str]:
    """解析 .bib 文件内容，返回 key → 格式化引用字符串的映射。

    Parse .bib file content, return key → formatted citation string
    mapping.

    Args:
        bib_text: Raw .bib file content (.bib 文件原始内容)

    Returns:
        Dict mapping cite key → one-line citation string
        (引用键 → 单行引用字符串的字典)
    """
    result: dict[str, str] = {}
    for entry_match in _ENTRY_START_RE.finditer(bib_text):
        entry_type = entry_match.group(1).strip().lower()
        key = entry_match.group(2).strip()
        # 从逗号之后开始查找条目体 (Find body starting after comma)
        body = _find_entry_body(bib_text, entry_match.end())
        if body is None:
            continue
        fields = _extract_fields(body)
        result[key] = _format_entry(fields, entry_type=entry_type)
    return result


def _extract_fields(fields_text: str) -> dict[str, str]:
    """提取条目中的所有字段 (Extract all fields from entry)."""
    fields: dict[str, str] = {}
    for m in _FIELD_RE.finditer(fields_text):
        field_name = m.group(1).lower()
        # 取第一个非 None 的捕获组 (First non-None capture group)
        value = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        fields[field_name] = value
    return fields


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and strip braces (合并空白并去掉花括号)."""
    return re.sub(r"\s+", " ", text.replace("{", "").replace("}", "")).strip()


def _format_person_ieee(name: str) -> str:
    """Format one author name to IEEE-like initials + family name (作者名 IEEE 风格化)."""
    n = _normalize_whitespace(name)
    if not n:
        return ""

    given: list[str]
    family: str
    if "," in n:
        parts = [p.strip() for p in n.split(",", 1)]
        family = parts[0]
        given = parts[1].split() if len(parts) > 1 else []
    else:
        words = n.split()
        if len(words) == 1:
            return words[0]
        family = words[-1]
        given = words[:-1]

    initials = " ".join(f"{w[0].upper()}." for w in given if w)
    if initials:
        return f"{initials} {family}"
    return family


def _format_authors_ieee(author_field: str) -> str:
    """Format BibTeX author field to IEEE-like author list (作者列表 IEEE 风格)."""
    authors = [_format_person_ieee(a) for a in author_field.split(" and ")]
    authors = [a for a in authors if a]
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    if len(authors) <= 3:
        return ", ".join(authors[:-1]) + f", and {authors[-1]}"
    return f"{authors[0]} et al."


def _format_entry(fields: dict[str, str], *, entry_type: str) -> str:
    """Format fields to a one-line IEEE-like reference string (一行 IEEE 风格引用)."""
    parts: list[str] = []

    authors = _format_authors_ieee(fields.get("author", ""))
    if authors:
        parts.append(authors)

    title = _normalize_whitespace(fields.get("title", ""))
    if title:
        if entry_type == "book":
            parts.append(title)
        else:
            parts.append(f'"{title}"')

    venue = _normalize_whitespace(
        fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
    )
    if venue:
        if entry_type == "inproceedings":
            parts.append(f"in {venue}")
        else:
            parts.append(venue)

    volume = _normalize_whitespace(fields.get("volume", ""))
    if volume:
        parts.append(f"vol. {volume}")

    number = _normalize_whitespace(fields.get("number", ""))
    if number:
        parts.append(f"no. {number}")

    pages = _normalize_whitespace(fields.get("pages", ""))
    if pages:
        parts.append(f"pp. {pages}")

    year = _normalize_whitespace(fields.get("year", ""))
    if year:
        parts.append(year)

    cleaned = [p.rstrip(".,; ") for p in parts if p]
    if not cleaned:
        return ""
    return ", ".join(cleaned) + "."
