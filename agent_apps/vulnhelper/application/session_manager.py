from __future__ import annotations

from datetime import datetime, timezone

from ..domain.enums import SessionState
from ..domain.models import VulnSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, VulnSession] = {}

    def get_or_create(self, session_id: str) -> VulnSession:
        session = self._sessions.get(session_id)
        if session is not None:
            return session
        now = _now()
        session = VulnSession(
            session_id=session_id,
            state=SessionState.IDLE,
            planned_args=None,
            last_query_result=None,
            last_report_markdown=None,
            last_filter_spec=None,
            created_at=now,
            updated_at=now,
            metadata={},
        )
        self._sessions[session_id] = session
        return session

    def save(self, session: VulnSession) -> None:
        session.updated_at = _now()
        self._sessions[session.session_id] = session

    def reset(self, session_id: str) -> VulnSession:
        session = self.get_or_create(session_id)
        now = _now()
        session.state = SessionState.IDLE
        session.planned_args = None
        session.last_query_result = None
        session.last_report_markdown = None
        session.last_filter_spec = None
        session.updated_at = now
        session.metadata.clear()
        return session

