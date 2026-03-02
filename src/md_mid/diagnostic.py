"""诊断系统：ERROR/WARNING/INFO 级别的诊断信息收集。"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class DiagLevel(enum.Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Position:
    line: int
    column: int = 1
    offset: int | None = None


@dataclass
class Diagnostic:
    level: DiagLevel
    message: str
    file: str
    position: Position | None = None

    def __str__(self) -> str:
        loc = f"{self.file}:{self.position.line}" if self.position else self.file
        return f"[{self.level.value}] {loc} - {self.message}"


class DiagCollector:
    def __init__(self, file: str) -> None:
        self.file = file
        self.diagnostics: list[Diagnostic] = []

    def _add(self, level: DiagLevel, message: str, position: Position | None = None) -> None:
        self.diagnostics.append(Diagnostic(level, message, self.file, position))

    def error(self, message: str, position: Position | None = None) -> None:
        self._add(DiagLevel.ERROR, message, position)

    def warning(self, message: str, position: Position | None = None) -> None:
        self._add(DiagLevel.WARNING, message, position)

    def info(self, message: str, position: Position | None = None) -> None:
        self._add(DiagLevel.INFO, message, position)

    @property
    def has_errors(self) -> bool:
        return any(d.level == DiagLevel.ERROR for d in self.diagnostics)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.level == DiagLevel.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.level == DiagLevel.WARNING]
