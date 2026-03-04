"""wenqiao (文桥): 以 Markdown 为唯一真源的学术写作工具。

Academic writing tool using Markdown as the canonical source.
"""

from wenqiao.api import (
    ConversionError,
    ConvertResult,
    convert,
    format_text,
    parse_document,
    validate_text,
)
from wenqiao.config import WenqiaoConfig
from wenqiao.diagnostic import Diagnostic
from wenqiao.genfig import FigureRunner
from wenqiao.genfig_openai import OpenAIFigureRunner
from wenqiao.nodes import Document

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "convert",
    "validate_text",
    "format_text",
    "parse_document",
    "ConvertResult",
    "ConversionError",
    "WenqiaoConfig",
    "Diagnostic",
    "Document",
    "FigureRunner",
    "OpenAIFigureRunner",
]
