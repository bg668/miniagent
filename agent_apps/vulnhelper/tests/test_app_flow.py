import asyncio

from agent_apps.vulnhelper.bootstrap import build_app
from agent_apps.vulnhelper.config import build_default_config


def test_offline_query_confirmation_report_and_drilldown_flow() -> None:
    app = build_app(build_default_config(), client=None)
    session_id = "offline-flow"

    confirmation = asyncio.run(app.handle_text(session_id=session_id, text="apache-superset 2.x 有没有高危漏洞，怎么修？"))
    assert confirmation.state == "waiting_for_confirmation"
    assert "apache-superset 2.x" in confirmation.markdown

    report = asyncio.run(app.handle_text(session_id=session_id, text="确认"))
    assert report.state == "report_ready"
    assert "【来源：本地漏洞库】" in report.markdown
    assert "CVE-2024-53949" in report.markdown

    drilldown = asyncio.run(app.handle_text(session_id=session_id, text="只看 CVE-2024-53949"))
    assert drilldown.state == "drilldown_ready"
    assert "CVE-2024-53949" in drilldown.markdown
