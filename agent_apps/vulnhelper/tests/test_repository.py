from agent_apps.vulnhelper.config import build_default_config
from agent_apps.vulnhelper.domain.enums import EntryMode, UserGoal
from agent_apps.vulnhelper.domain.models import QueryPlan
from agent_apps.vulnhelper.infra.sqlite_repository import SQLiteVulnRepository


def test_repository_can_list_candidates() -> None:
    config = build_default_config()
    repo = SQLiteVulnRepository(config.db_path)
    plan = QueryPlan(entry_mode=EntryMode.PRODUCT_VERSION, product="tensorflow-cpu", user_goal=UserGoal.TRIAGE)
    rows = repo.list_candidates(plan)
    assert isinstance(rows, list)

