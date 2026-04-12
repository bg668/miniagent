from __future__ import annotations

from openai import AsyncOpenAI

from .agents.factory import AgentFactory
from .agentsdk.adapters.openai_chatcompletions import OpenAIChatCompletionsAdapter
from .application.orchestrator import VulnHelperOrchestrator
from .application.request_router import RequestRouter
from .application.session_manager import SessionManager
from .config import VulnHelperConfig
from .infra.sqlite_repository import SQLiteVulnRepository
from .infra.session_cache import InMemoryQueryCache
from .renderers.confirmation_renderer import ConfirmationRenderer
from .renderers.report_renderer import ReportRenderer
from .renderers.table_renderer import TableRenderer
from .tools.filter_cached_results import FilterCachedResultsTool
from .tools.query_vulns import QueryVulnsTool


_UNSET = object()


def _build_adapters(config: VulnHelperConfig, client: AsyncOpenAI | None | object) -> dict[str, OpenAIChatCompletionsAdapter | None]:
    if client is None:
        return {profile_ref: None for profile_ref in config.required_profile_refs()}

    if client is not _UNSET:
        shared = OpenAIChatCompletionsAdapter(client)
        return {profile_ref: shared for profile_ref in config.required_profile_refs()}

    adapters: dict[str, OpenAIChatCompletionsAdapter | None] = {}
    for profile_ref in config.required_profile_refs():
        profile = config.llm_profiles[profile_ref]
        if not profile.api_key:
            adapters[profile_ref] = None
            continue
        adapters[profile_ref] = OpenAIChatCompletionsAdapter(
            AsyncOpenAI(api_key=profile.api_key, base_url=profile.base_url or None)
        )
    return adapters


def build_app(config: VulnHelperConfig, client: AsyncOpenAI | None | object = _UNSET) -> VulnHelperOrchestrator:
    adapters = _build_adapters(config, client)
    session_manager = SessionManager()
    repository = SQLiteVulnRepository(config.db_path)
    query_cache = InMemoryQueryCache()

    query_tool = QueryVulnsTool(repository=repository, query_cache=query_cache)
    filter_tool = FilterCachedResultsTool(query_cache=query_cache)

    renderers = {
        "confirmation": ConfirmationRenderer(config.confirmation_template_path),
        "report": ReportRenderer(config.report_template_path, max_rows=config.max_table_rows),
        "table": TableRenderer(config.table_template_path, max_rows=config.max_table_rows),
    }

    factory = AgentFactory(
        config=config,
        adapters=adapters,
        session_manager=session_manager,
        query_tool=query_tool,
        filter_tool=filter_tool,
    )

    return VulnHelperOrchestrator(
        session_manager=session_manager,
        request_router=RequestRouter(),
        planner_agent=factory.build_planner_agent(),
        executor_agent=factory.build_executor_agent(),
        analyst_agent=factory.build_analyst_agent(),
        workflow=config.workflow,
        confirmation_renderer=renderers["confirmation"],
        report_renderer=renderers["report"],
        table_renderer=renderers["table"],
        query_cache=query_cache,
    )
