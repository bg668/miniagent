from agent_apps.vulnhelper.config import build_default_config


def test_build_default_config_reads_vulnhelper_config_json() -> None:
    config = build_default_config()

    assert config.config_json_path.name == "config.json"
    assert config.subagents_dir.name == "subagents"
    assert config.planner_model.id == "glm-5"
    assert config.executor_model.base_url == "https://coding.dashscope.aliyuncs.com/v1"
    assert config.planner_subagent.provider_ref == "dashscope_glm"
    assert config.planner_prompt_path.name == "planner_system.txt"
    assert config.workflow.route_for("new_query") == ("planner",)
    assert config.workflow.route_for("confirm") == ("executor", "analyst")
    assert config.workflow.route_for("drilldown") == ("executor",)
