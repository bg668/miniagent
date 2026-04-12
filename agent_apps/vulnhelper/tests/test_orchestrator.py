from agent_apps.vulnhelper.application.request_router import RequestRouter, RoutedIntent
from agent_apps.vulnhelper.application.session_manager import SessionManager


def test_router_defaults_to_new_query() -> None:
    manager = SessionManager()
    session = manager.get_or_create("s1")
    router = RequestRouter()
    assert router.route(session, "tensorflow-cpu 2.4.1 有漏洞吗") == RoutedIntent.NEW_QUERY

