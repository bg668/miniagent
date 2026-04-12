from __future__ import annotations

from pathlib import Path
from string import Template

from ..domain.confirmation import build_confirmation_target
from ..domain.models import QueryPlan


class ConfirmationRenderer:
    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def render(self, plan: QueryPlan, confirmation_text: str) -> str:
        template = Template(self._template_path.read_text(encoding="utf-8"))
        return template.safe_substitute(
            target=build_confirmation_target(plan),
            entry_mode=plan.entry_mode.value,
            confirmation_text=confirmation_text.strip(),
        )

