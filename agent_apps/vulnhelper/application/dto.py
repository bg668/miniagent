from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserTurnInput:
    session_id: str
    text: str


@dataclass(slots=True)
class UserTurnOutput:
    session_id: str
    state: str
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)

