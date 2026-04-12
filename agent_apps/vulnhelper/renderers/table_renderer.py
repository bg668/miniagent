from __future__ import annotations

from pathlib import Path
from string import Template

from .markdown_helpers import markdown_table, truncate


class TableRenderer:
    def __init__(self, template_path: Path, max_rows: int = 50) -> None:
        self._template_path = template_path
        self._max_rows = max_rows

    def render(self, rows: list[dict[str, str]]) -> str:
        compact_rows = [
            {
                "CVE 编号": row.get("cve_id", ""),
                "风险": row.get("risk_label", ""),
                "摘要": truncate(row.get("summary", ""), 66),
            }
            for row in rows[: self._max_rows]
        ]
        template = Template(self._template_path.read_text(encoding="utf-8"))
        return template.safe_substitute(rows_table=markdown_table(compact_rows, ["CVE 编号", "风险", "摘要"]))

