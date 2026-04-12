from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agentsdk import ModelInfo


def _default_root() -> Path:
    return Path(__file__).resolve().parent


@dataclass(slots=True)
class LLMProfileConfig:
    name: str
    provider: str
    api: str
    base_url: str | None
    api_key: str | None
    default_model: str


@dataclass(slots=True)
class SubagentConfig:
    name: str
    role: str
    provider_ref: str
    model: ModelInfo
    prompt_path: Path
    temperature: float = 0.0
    max_tokens: int | None = None


@dataclass(slots=True)
class WorkflowConfig:
    routes: dict[str, tuple[str, ...]]

    def route_for(self, name: str) -> tuple[str, ...]:
        return self.routes.get(name, ())


@dataclass(slots=True)
class VulnHelperConfig:
    root_dir: Path
    config_json_path: Path
    subagents_dir: Path
    db_path: Path
    llm_profiles: dict[str, LLMProfileConfig]
    planner_subagent: SubagentConfig
    executor_subagent: SubagentConfig
    analyst_subagent: SubagentConfig
    workflow: WorkflowConfig
    output_contracts_path: Path
    report_template_path: Path
    confirmation_template_path: Path
    table_template_path: Path
    max_table_rows: int = 50

    @property
    def planner_model(self) -> ModelInfo:
        return self.planner_subagent.model

    @property
    def executor_model(self) -> ModelInfo:
        return self.executor_subagent.model

    @property
    def analyst_model(self) -> ModelInfo:
        return self.analyst_subagent.model

    @property
    def planner_prompt_path(self) -> Path:
        return self.planner_subagent.prompt_path

    @property
    def executor_prompt_path(self) -> Path:
        return self.executor_subagent.prompt_path

    @property
    def analyst_prompt_path(self) -> Path:
        return self.analyst_subagent.prompt_path

    @property
    def planner_temperature(self) -> float:
        return self.planner_subagent.temperature

    @property
    def executor_temperature(self) -> float:
        return self.executor_subagent.temperature

    @property
    def analyst_temperature(self) -> float:
        return self.analyst_subagent.temperature

    @property
    def planner_max_tokens(self) -> int | None:
        return self.planner_subagent.max_tokens

    @property
    def executor_max_tokens(self) -> int | None:
        return self.executor_subagent.max_tokens

    @property
    def analyst_max_tokens(self) -> int | None:
        return self.analyst_subagent.max_tokens

    @property
    def api_key(self) -> str | None:
        return self.llm_profiles[self.planner_subagent.provider_ref].api_key

    @property
    def base_url(self) -> str | None:
        return self.llm_profiles[self.planner_subagent.provider_ref].base_url

    def required_profile_refs(self) -> list[str]:
        refs = {
            self.planner_subagent.provider_ref,
            self.executor_subagent.provider_ref,
            self.analyst_subagent.provider_ref,
        }
        return sorted(refs)

    def missing_api_key_profile_refs(self) -> list[str]:
        missing: list[str] = []
        for profile_ref in self.required_profile_refs():
            profile = self.llm_profiles[profile_ref]
            if not profile.api_key:
                missing.append(profile_ref)
        return missing


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _resolve_config_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        import os

        return os.environ.get(value[2:-1], "")
    return value


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _build_profile(name: str, payload: dict[str, Any], inherited_api_key: Any = None) -> LLMProfileConfig:
    model_block = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    return LLMProfileConfig(
        name=name,
        provider=str(_coalesce(payload.get("provider"), model_block.get("provider"), "openai")),
        api=str(_coalesce(payload.get("api"), model_block.get("api"), "chat.completions")),
        base_url=_coalesce(
            _resolve_config_value(payload.get("base_url")),
            _resolve_config_value(model_block.get("base_url")),
        ),
        api_key=_coalesce(
            _resolve_config_value(payload.get("api_key")),
            _resolve_config_value(inherited_api_key),
        ),
        default_model=str(
            _coalesce(
                payload.get("default_model"),
                payload.get("model"),
                model_block.get("id"),
                model_block.get("name"),
                "gpt-4o-mini",
            )
        ),
    )


def _load_profiles(payload: dict[str, Any]) -> dict[str, LLMProfileConfig]:
    profile_payloads = payload.get("llm_profiles")
    if isinstance(profile_payloads, dict) and profile_payloads:
        inherited_api_key = payload.get("api_key")
        return {
            name: _build_profile(name, value if isinstance(value, dict) else {}, inherited_api_key)
            for name, value in profile_payloads.items()
        }

    # Backward-compatible fallback to the previous single-profile layout.
    return {
        "default": _build_profile("default", payload, payload.get("api_key")),
    }


def _build_model_info(model_name: str, profile: LLMProfileConfig) -> ModelInfo:
    return ModelInfo(
        id=model_name,
        name=model_name,
        provider=profile.provider,
        api=profile.api,
        base_url=profile.base_url or "",
    )


def _load_workflow(payload: dict[str, Any], known_subagents: set[str]) -> WorkflowConfig:
    default_routes: dict[str, tuple[str, ...]] = {
        "new_query": ("planner",),
        "confirm": ("executor", "analyst"),
        "drilldown": ("executor",),
    }
    raw_routes = payload.get("workflow_routes")
    routes: dict[str, tuple[str, ...]] = dict(default_routes)

    if isinstance(raw_routes, dict):
        for route_name, phases in raw_routes.items():
            if not isinstance(route_name, str):
                continue
            if not isinstance(phases, list) or not all(isinstance(item, str) for item in phases):
                raise ValueError(f"workflow_routes.{route_name} 必须是字符串数组")
            routes[route_name] = tuple(phases)

    required_routes = {"new_query", "confirm", "drilldown"}
    missing_routes = sorted(route for route in required_routes if route not in routes)
    if missing_routes:
        raise ValueError(f"workflow_routes 缺少必需路由: {', '.join(missing_routes)}")

    for route_name, phases in routes.items():
        unknown = [phase for phase in phases if phase not in known_subagents]
        if unknown:
            raise ValueError(f"workflow_routes.{route_name} 引用了未知 subagent: {', '.join(unknown)}")

    return WorkflowConfig(routes=routes)


def _load_subagent(
    *,
    root: Path,
    subagents_dir: Path,
    payload: dict[str, Any],
    profiles: dict[str, LLMProfileConfig],
    name: str,
    default_prompt_file: str,
    default_role: str,
) -> SubagentConfig:
    file_payload = _read_json_file(subagents_dir / f"{name}.json")
    agent_payload = file_payload or (payload.get(name) if isinstance(payload.get(name), dict) else {})

    provider_ref = str(agent_payload.get("provider_ref") or payload.get("default_provider_ref") or next(iter(profiles)))
    if provider_ref not in profiles:
        raise ValueError(f"Unknown provider_ref '{provider_ref}' for subagent '{name}'")

    profile = profiles[provider_ref]
    model_name = str(agent_payload.get("model") or profile.default_model)
    prompt_file = str(agent_payload.get("system_prompt_file") or default_prompt_file)
    return SubagentConfig(
        name=name,
        role=str(agent_payload.get("role") or default_role),
        provider_ref=provider_ref,
        model=_build_model_info(model_name, profile),
        prompt_path=_resolve_path(root, prompt_file),
        temperature=float(agent_payload.get("temperature", 0.0)),
        max_tokens=agent_payload.get("max_tokens"),
    )


def build_default_config(root_dir: Path | None = None) -> VulnHelperConfig:
    root = root_dir or _default_root()
    prompts_dir = root / "prompts"
    templates_dir = root / "templates"
    config_json_path = root / "config.json"
    payload = _read_json_file(config_json_path)
    subagents_dir = _resolve_path(root, str(payload.get("subagents_dir") or "subagents"))
    profiles = _load_profiles(payload)
    known_subagents = {"planner", "executor", "analyst"}

    return VulnHelperConfig(
        root_dir=root,
        config_json_path=config_json_path,
        subagents_dir=subagents_dir,
        db_path=root / "data" / "vulns.db",
        llm_profiles=profiles,
        planner_subagent=_load_subagent(
            root=root,
            subagents_dir=subagents_dir,
            payload=payload,
            profiles=profiles,
            name="planner",
            default_prompt_file=str(prompts_dir / "planner_system.txt"),
            default_role="阶段一规划代理",
        ),
        executor_subagent=_load_subagent(
            root=root,
            subagents_dir=subagents_dir,
            payload=payload,
            profiles=profiles,
            name="executor",
            default_prompt_file=str(prompts_dir / "executor_system.txt"),
            default_role="执行代理",
        ),
        analyst_subagent=_load_subagent(
            root=root,
            subagents_dir=subagents_dir,
            payload=payload,
            profiles=profiles,
            name="analyst",
            default_prompt_file=str(prompts_dir / "analyst_system.txt"),
            default_role="安全研判代理",
        ),
        workflow=_load_workflow(payload, known_subagents),
        output_contracts_path=prompts_dir / "output_contracts.md",
        report_template_path=templates_dir / "report.md.j2",
        confirmation_template_path=templates_dir / "confirmation.md.j2",
        table_template_path=templates_dir / "table.md.j2",
        max_table_rows=int(payload.get("max_table_rows", 50)),
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
