# VulnHelper

基于 `agentsdk` 的漏洞查询助手骨架工程。

当前目录已完成：

- 设计文档
- 目录结构
- 代码骨架
- 精简版 vendored `agentsdk` 运行时副本，位于 `agent_apps/vulnhelper/agentsdk/`

当前目录尚未完成：

- 完整提示词调优
- 端到端漏洞命中精度验证
- 与 golden 样例的最终对齐

## 运行配置

- LLM 运行配置固定读取 [config.json](/Users/bg/project/uu-work/agent_apps/vulnhelper/config.json)
- `api_key` 支持直接填写，或写成 `${ENV_VAR}` 形式引用环境变量
- `llm_profiles` 负责统一维护 provider / base_url / api_key / 默认模型
- `subagents/*.json` 负责为 Planner、Executor、Analyst 指定 `provider_ref`、提示词和局部参数
- `workflow_routes` 显式声明 orchestrator 的阶段路由，例如 `new_query -> planner`、`confirm -> executor -> analyst`、`drilldown -> executor`

## 目录

- [概要设计](/Users/bg/project/uu-work/agent_apps/vulnhelper/概要设计.md)
- [详细设计](/Users/bg/project/uu-work/agent_apps/vulnhelper/详细设计.md)
- [目录结构设计](/Users/bg/project/uu-work/agent_apps/vulnhelper/目录结构设计.md)
