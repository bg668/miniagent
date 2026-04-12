import asyncio

from agent_apps.vulnhelper.config import build_default_config
from agent_apps.vulnhelper.domain.enums import EntryMode, UserGoal
from agent_apps.vulnhelper.infra.session_cache import InMemoryQueryCache
from agent_apps.vulnhelper.infra.sqlite_repository import SQLiteVulnRepository
from agent_apps.vulnhelper.tools.query_vulns import QueryVulnsTool


def test_query_tool_writes_cache() -> None:
    config = build_default_config()
    tool = QueryVulnsTool(repository=SQLiteVulnRepository(config.db_path), query_cache=InMemoryQueryCache())
    payload = {
        "session_id": "s1",
        "plan": {
            "entry_mode": EntryMode.PRODUCT_VERSION.value,
            "product": "tensorflow-cpu",
            "version_spec": "2.4.1",
            "user_goal": UserGoal.TRIAGE.value,
        },
    }
    result = asyncio.run(tool.execute("t1", payload))
    assert result.details["cache_id"]

