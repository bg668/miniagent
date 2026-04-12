from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..domain.models import QueryPlan


class SQLiteVulnRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_candidates(self, plan: QueryPlan) -> list[dict[str, Any]]:
        sql = 'select * from vulnerability_records where 1=1'
        params: list[Any] = []

        if plan.vuln_id:
            sql += ' and upper("basicinfo.cve_id") = upper(?)'
            params.append(plan.vuln_id)
        elif plan.product:
            sql += ' and lower("impact.vendors_products") like ?'
            params.append(f"%{plan.product.lower()}%")

        if plan.malicious_only:
            sql += ' and (lower("basicinfo.description") like ? or lower("impact.vendors_products") like ?)'
            params.extend(["%malicious%", "%malicious%"])

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

