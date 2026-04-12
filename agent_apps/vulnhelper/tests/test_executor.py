import asyncio
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from agent_apps.vulnhelper.agents.executor import ExecutorAgentRunner, build_executor_agent
from agent_apps.vulnhelper.agentsdk import AgentContext, AssistantMessage, BeforeToolCallContext, ToolCallContent
from agent_apps.vulnhelper.application.session_manager import SessionManager
from agent_apps.vulnhelper.config import build_default_config
from agent_apps.vulnhelper.domain.enums import EntryMode, SessionState, UserGoal
from agent_apps.vulnhelper.domain.models import QueryPlan
from agent_apps.vulnhelper.infra.session_cache import InMemoryQueryCache
from agent_apps.vulnhelper.infra.sqlite_repository import SQLiteVulnRepository
from agent_apps.vulnhelper.tools.filter_cached_results import FilterCachedResultsTool
from agent_apps.vulnhelper.tools.query_vulns import QueryVulnsTool


class DummyAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(messages=())

    async def prompt(self, *_args, **_kwargs) -> None:
        return None

    async def wait_for_idle(self) -> None:
        return None


def test_execute_query_uses_local_tool_when_no_agent_is_available() -> None:
    config = build_default_config()
    cache = InMemoryQueryCache()
    runner = ExecutorAgentRunner(
        None,
        QueryVulnsTool(repository=SQLiteVulnRepository(config.db_path), query_cache=cache),
        FilterCachedResultsTool(query_cache=cache),
    )

    asyncio.run(
        runner.execute_query(
            "s1",
            {
                "entry_mode": EntryMode.PRODUCT_VERSION.value,
                "product": "apache-superset",
                "version_spec": "2.x",
                "risk_levels": ["high", "critical"],
                "user_goal": UserGoal.TRIAGE.value,
            },
        )
    )

    cached = cache.get("s1")
    assert cached is not None
    assert cached.summary.filtered_count > 0


def test_execute_query_raises_when_agent_does_not_call_required_tool() -> None:
    config = build_default_config()
    cache = InMemoryQueryCache()
    runner = ExecutorAgentRunner(
        DummyAgent(),
        QueryVulnsTool(repository=SQLiteVulnRepository(config.db_path), query_cache=cache),
        FilterCachedResultsTool(query_cache=cache),
    )

    with pytest.raises(RuntimeError, match="query_vulns"):
        asyncio.run(
            runner.execute_query(
                "s1",
                {
                    "entry_mode": EntryMode.PRODUCT_VERSION.value,
                    "product": "apache-superset",
                    "version_spec": "2.x",
                    "risk_levels": ["high", "critical"],
                    "user_goal": UserGoal.TRIAGE.value,
                },
            )
        )


def test_before_tool_call_allows_query_after_confirmation_transitions_to_executing() -> None:
    config = build_default_config()
    cache = InMemoryQueryCache()
    session_manager = SessionManager()
    query_tool = QueryVulnsTool(repository=SQLiteVulnRepository(config.db_path), query_cache=cache)
    filter_tool = FilterCachedResultsTool(query_cache=cache)
    runner = build_executor_agent(
        lambda *_args, **_kwargs: None,
        config.executor_model,
        config.executor_prompt_path,
        session_manager,
        query_tool,
        filter_tool,
    )

    session = session_manager.get_or_create("s1")
    session.planned_args = QueryPlan(
        entry_mode=EntryMode.PRODUCT_VERSION,
        product="apache-superset",
        version_spec="2.x",
        risk_levels=["high", "critical"],
        user_goal=UserGoal.TRIAGE,
    )
    session.state = SessionState.EXECUTING_QUERY
    session_manager.save(session)

    hook = runner._agent.before_tool_call
    assert hook is not None
    result = hook(
        BeforeToolCallContext(
            assistant_message=AssistantMessage(),
            tool_call=ToolCallContent(id="call-1", name="query_vulns", arguments={}),
            args={"session_id": session.session_id, "plan": asdict(session.planned_args)},
            context=AgentContext(),
        ),
        None,
    )

    assert result is None
