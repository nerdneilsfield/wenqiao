"""Tests for the public Python API (公共 Python API 测试).

Covers convert(), validate_text(), format_text(), and parse_document().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from md_mid import (
    ConversionError,
    ConvertResult,
    Document,
    MdMidConfig,
    convert,
    format_text,
    parse_document,
    validate_text,
)
from md_mid.diagnostic import DiagLevel

# -- Fixtures (测试固件) -----------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL_MD = FIXTURES / "minimal.mid.md"
CITE_REF_MD = FIXTURES / "cite_ref.mid.md"

SIMPLE_MD = "# Hello\n\nWorld.\n"


# -- convert() tests (convert 函数测试) --------------------------------------


def test_convert_string_to_latex() -> None:
    """Convert a simple string to LaTeX (简单字符串转 LaTeX)."""
    result = convert(SIMPLE_MD)
    assert isinstance(result, ConvertResult)
    assert "\\section{Hello}" in result.text or "Hello" in result.text
    assert "World" in result.text


def test_convert_file_path() -> None:
    """Convert from a file Path (从文件路径转换)."""
    result = convert(MINIMAL_MD)
    assert isinstance(result, ConvertResult)
    assert "Hello World" in result.text
    assert len(result.text) > 0


def test_convert_to_markdown() -> None:
    """Convert to Markdown target (转换为 Markdown 格式)."""
    result = convert(SIMPLE_MD, target="markdown")
    assert "Hello" in result.text
    assert "World" in result.text


def test_convert_to_html() -> None:
    """Convert to HTML target (转换为 HTML 格式)."""
    result = convert(SIMPLE_MD, target="html")
    assert "Hello" in result.text
    assert "World" in result.text


def test_convert_with_mode() -> None:
    """Convert with mode=body omits preamble (body 模式省略前导码)."""
    result_full = convert(SIMPLE_MD, target="latex", mode="full")
    result_body = convert(SIMPLE_MD, target="latex", mode="body")
    # full mode contains documentclass, body mode does not (full 模式含 documentclass)
    assert "\\documentclass" in result_full.text
    assert "\\documentclass" not in result_body.text


def test_convert_with_locale() -> None:
    """Convert with locale parameter (使用 locale 参数转换)."""
    result = convert(SIMPLE_MD, target="latex", locale="en")
    assert isinstance(result.config, MdMidConfig)
    # Config should reflect locale=en (配置应反映 locale=en)
    assert result.config.locale == "en"


def test_convert_with_config_dict() -> None:
    """Convert with dict overrides (使用字典覆盖转换)."""
    result = convert(SIMPLE_MD, config={"mode": "body", "locale": "en"})
    assert "\\documentclass" not in result.text


def test_convert_with_config_object() -> None:
    """Convert with MdMidConfig directly (直接使用 MdMidConfig 转换)."""
    cfg = MdMidConfig(mode="body", locale="en")
    result = convert(SIMPLE_MD, config=cfg)
    assert result.config is cfg
    assert "\\documentclass" not in result.text


def test_convert_with_template(tmp_path: Path) -> None:
    """Convert with template YAML (使用模板 YAML 转换)."""
    tpl = tmp_path / "test.yaml"
    tpl.write_text("documentclass: report\n", encoding="utf-8")
    result = convert(SIMPLE_MD, template=tpl)
    assert "report" in result.text


def test_convert_with_bib_path(tmp_path: Path) -> None:
    """Convert with bib file path for markdown target (Markdown 目标使用 bib 文件路径)."""
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(
        "@article{wang2024,\n  author={Wang, X},\n  title={Test},\n  year={2024}\n}\n",
        encoding="utf-8",
    )
    md = "See [Wang](cite:wang2024).\n"
    result = convert(md, target="markdown", bib=bib_file)
    assert "Wang" in result.text


def test_convert_with_bib_string() -> None:
    """Convert with raw .bib text content (使用原始 .bib 文本内容转换)."""
    bib_text = "@article{wang2024,\n  author={Wang, X},\n  title={Test},\n  year={2024}\n}\n"
    md = "See [Wang](cite:wang2024).\n"
    result = convert(md, target="markdown", bib=bib_text)
    assert "Wang" in result.text


def test_convert_with_bib_dict() -> None:
    """Convert with pre-parsed bib dict (使用预解析的 bib 字典转换)."""
    bib_dict = {"wang2024": "Wang. Test. 2024."}
    md = "See [Wang](cite:wang2024).\n"
    result = convert(md, target="markdown", bib=bib_dict)
    assert "Wang" in result.text


def test_convert_strict_raises() -> None:
    """strict=True raises ConversionError on diagnostic errors (严格模式有错误时抛出异常)."""
    # Unmatched begin/end triggers an error diagnostic (不匹配的 begin/end 触发错误诊断)
    md = "<!-- begin: figure -->\nHello\n"
    with pytest.raises(ConversionError) as exc_info:
        convert(md, strict=True)
    assert len(exc_info.value.diagnostics) > 0


def test_convert_result_attributes() -> None:
    """Verify ConvertResult attributes (验证 ConvertResult 属性)."""
    result = convert(SIMPLE_MD)
    assert isinstance(result.text, str)
    assert isinstance(result.diagnostics, list)
    assert isinstance(result.config, MdMidConfig)
    assert isinstance(result.document, Document)


def test_convert_invalid_target() -> None:
    """Invalid target raises ValueError (无效目标格式抛出 ValueError)."""
    with pytest.raises(ValueError, match="Unsupported target"):
        convert(SIMPLE_MD, target="pdf")


# -- validate_text() tests (validate_text 函数测试) --------------------------


def test_validate_text_clean() -> None:
    """Clean document returns no diagnostics (干净文档无诊断信息)."""
    diags = validate_text(SIMPLE_MD)
    # Simple doc should have no errors (简单文档应无错误)
    errors = [d for d in diags if d.level == DiagLevel.ERROR]
    assert len(errors) == 0


def test_validate_text_missing_cite() -> None:
    """Missing citation key produces a warning (缺失引用键产生警告)."""
    md = "See [ref](cite:nonexistent_key).\n"
    # Provide empty bib to trigger missing-key warning (提供空 bib 触发缺失键警告)
    diags = validate_text(md, bib={})
    warnings = [d for d in diags if d.level == DiagLevel.WARNING]
    assert any("nonexistent_key" in d.message for d in warnings)


def test_validate_text_strict_raises() -> None:
    """strict=True raises on unmatched begin (严格模式对不匹配 begin 抛出异常)."""
    md = "<!-- begin: figure -->\nHello\n"
    with pytest.raises(ConversionError):
        validate_text(md, strict=True)


# -- format_text() tests (format_text 函数测试) ------------------------------


def test_format_text_roundtrip() -> None:
    """Formatting is idempotent on already-formatted text (对已格式化文本幂等)."""
    formatted = format_text(SIMPLE_MD)
    assert isinstance(formatted, str)
    # Re-formatting should produce the same result (再次格式化应产生相同结果)
    reformatted = format_text(formatted)
    assert formatted == reformatted


def test_format_text_normalises() -> None:
    """format_text produces normalized output (格式化产生规范化输出)."""
    result = format_text(SIMPLE_MD)
    assert "Hello" in result
    assert len(result) > 0


# -- parse_document() tests (parse_document 函数测试) ------------------------


def test_parse_document_returns_document() -> None:
    """parse_document returns a Document instance (返回 Document 实例)."""
    doc = parse_document(SIMPLE_MD)
    assert isinstance(doc, Document)
    assert len(doc.children) > 0


def test_parse_document_from_path() -> None:
    """parse_document accepts a Path input (接受 Path 输入)."""
    doc = parse_document(MINIMAL_MD)
    assert isinstance(doc, Document)
    assert len(doc.children) > 0
