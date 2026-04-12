from __future__ import annotations

from pathlib import Path
from string import Template

from ..domain.models import CachedQueryResult
from .markdown_helpers import markdown_table, truncate


class ReportRenderer:
    def __init__(self, template_path: Path, max_rows: int = 50) -> None:
        self._template_path = template_path
        self._max_rows = max_rows

    def render(self, result: CachedQueryResult, expert_analysis: str, fix_strategy: str) -> str:
        summary = result.summary
        rows = [
            {
                "CVE 编号": record.cve_id or record.record_id,
                "风险": (record.risk_level or "unknown"),
                "摘要": truncate(record.description, 66),
            }
            for record in result.matched_records[: self._max_rows]
        ]
        template = Template(self._template_path.read_text(encoding="utf-8"))
        return template.safe_substitute(
            entry_label=summary.entry_label,
            stats_line=f"初始候选 {summary.initial_candidate_count} 条；过滤后 {summary.filtered_count} 条。",
            target_label=summary.target_label or "未明确目标",
            conclusion=summary.conclusion,
            expert_analysis=expert_analysis.strip(),
            fix_strategy=fix_strategy.strip(),
            rows_table=markdown_table(rows, ["CVE 编号", "风险", "摘要"]),
        )

