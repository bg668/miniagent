from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


def log_agent_event(event: Any) -> None:
    logger.debug("vulnhelper event: %s", getattr(event, "type", type(event).__name__))
