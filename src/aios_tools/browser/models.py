from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SemanticLocator:
    kind: Literal["role", "label", "test_id", "text"]
    value: str
    accessible_name: str | None = None
    exact: bool = True

    def __post_init__(self) -> None:
        if self.kind not in {"role", "label", "test_id", "text"}:
            raise ValueError("unsupported semantic locator kind")
        if not self.value or len(self.value) > 512:
            raise ValueError("semantic locator value is invalid")
        if self.accessible_name is not None and len(self.accessible_name) > 512:
            raise ValueError("semantic locator accessible_name is invalid")
