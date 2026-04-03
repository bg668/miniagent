下面是可直接提供给 AI coder 的实现任务书。

---

# 多 Agent 轻量协同系统 v2.0 实现任务书

## 1. 任务目标

你需要实现一个**可扩展的通用多 Agent 协同框架首版**。

该系统用于处理**单一复杂任务**。任务需要由多个角色协作完成，包括：

* Planner：负责拆解任务
* Executor：负责执行任务
* Reviewer：负责审核结果
* Recorder：首版不作为独立 Agent，实现为系统级审计记录能力

首版目标不是实现一个完整的自治智能体平台，而是实现一个：

* 可闭环
* 可审计
* 可恢复
* 可测试
* 可扩展

的多 Agent 协作框架。

---

## 2. 必须遵守的总体约束

### 2.1 架构约束

必须严格按以下架构实现：

* 采用**半中心化控制**
* 由 **Orchestrator** 作为唯一流程推进者
* Agent 不允许自治扫描全局任务池
* 文件系统是状态真源
* Agent 首版只支持**单次调用模式**
* 不允许默认实现常驻轮询 Agent

### 2.2 状态真源约束

以下内容必须落盘：

* 全局状态
* 任务定义
* 执行产物
* 审计日志

内存中的 prompt、messages、临时上下文都不能作为系统事实真源。

### 2.3 开发方式约束

你必须采用**分阶段 TDD 开发**：

* 先写测试
* 再写实现
* 当前阶段测试未通过，不得进入下一阶段
* 不允许一次性生成整套系统代码
* 不允许先写一个“大而全版本”再补测试

### 2.4 首版边界约束

首版明确**不实现**以下内容：

* 异步 inbox 消息机制
* 多进程并发任务认领
* 强一致消息队列
* 常驻轮询 Agent
* 自动记忆压缩
* 数据库后端
* 分布式部署
* 多任务池并发工作流
* 独立 Recorder Agent 进程

---

## 3. 你要交付的内容

你最终需要交付以下内容：

### 3.1 代码模块

至少包括：

* `workspace_store.py`
* `task_manager.py`
* `orchestrator.py`
* `agent_runner.py`
* `tool_sandbox.py`
* `schemas.py`
* `audit_log.py`

### 3.2 测试代码

至少包括：

* `tests/test_workspace.py`
* `tests/test_task_manager.py`
* `tests/test_orchestrator_mock_flow.py`
* `tests/test_tool_sandbox.py`

### 3.3 演示脚本

至少包括：

* 一个可运行的 mock 流程 demo
* 能跑通 Planner → Executor → Reviewer → 完成/失败 的闭环

### 3.4 文档

至少包括：

* README
* 模块说明
* 如何运行测试
* 如何运行 demo

---

## 4. 必须实现的目录结构

你实现后的工作空间目录必须满足以下结构：

```text
/workspaces/task_{uuid}/
 ├── meta.json
 ├── state.json
 ├── context.json
 ├── event_log.jsonl
 ├── tasks/
 │    ├── task_root.json
 │    ├── task_plan_1.json
 │    ├── task_exec_1.json
 │    └── task_review_1.json
 └── artifacts/
      ├── draft_1.md
      ├── review_1.json
      └── final_output.md
```

要求：

* 所有关键状态都写入该目录
* 不允许把核心状态只保存在内存里
* `event_log.jsonl` 必须采用追加写

---

## 5. 必须实现的数据模型

### 5.1 Task Node

必须支持以下字段：

```json
{
  "id": "string",
  "subject": "string",
  "description": "string",
  "role": "planner | executor | reviewer",
  "status": "pending | in_progress | completed | failed",
  "owner": "string | null",
  "blockedBy": ["string"],
  "input_refs": ["string"],
  "output_refs": ["string"],
  "parent_task_id": "string | null",
  "retry_count": 0,
  "failure_reason": "string | null",
  "priority": 100,
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

### 5.2 State

必须支持以下字段：

```json
{
  "workflow_status": "planning | executing | reviewing | completed | failed",
  "current_task_id": "string | null",
  "current_role": "planner | executor | reviewer | null",
  "retry_limit": 2,
  "review_round": 0,
  "last_error": null
}
```

### 5.3 Event

必须支持以下字段：

```json
{
  "event_id": "uuid",
  "timestamp": "iso8601",
  "kind": "workflow | task | agent | tool",
  "type": "string",
  "task_id": "string | null",
  "role": "string | null",
  "status": "string | null",
  "summary": "string",
  "details": {
    "artifact_refs": [],
    "error": null,
    "extra": {}
  }
}
```

### 5.4 Tool Result

所有工具返回值必须标准化为：

```json
{
  "status": "ok | failed",
  "output": "string | object | null",
  "error": "string | null"
}
```

---

## 6. 必须实现的模块职责

## 6.1 WorkspaceStore

负责：

* 初始化工作空间
* 原子写入 JSON
* 追加写入 JSONL
* 读写文本产物
* 读取 task/state/context/artifact

要求：

* 对覆盖写必须使用 `.tmp + fsync + os.replace`
* 不允许直接 `open(..., 'w')` 覆盖核心状态文件
* 不负责流程控制

必须提供的能力：

* `init_workspace(...)`
* `read_json(...)`
* `write_json_atomic(...)`
* `append_jsonl(...)`
* `read_text(...)`
* `write_text(...)`

---

## 6.2 TaskManager

负责：

* 创建任务
* 获取下一个可执行任务
* 更新任务状态
* 标记任务完成
* 标记任务失败
* 自动解除依赖

可执行任务的判定规则：

* `status == pending`
* `blockedBy == []`

任务选择规则：

1. `priority` 最小优先
2. `created_at` 最早优先

说明：

* 首版假设只有一个 Orchestrator
* 你不需要解决多进程并发 claim

必须提供的能力：

* `create_task(task)`
* `get_next_runnable_task()`
* `update_task(task_id, patch)`
* `mark_task_completed(task_id, output_refs)`
* `mark_task_failed(task_id, reason)`

---

## 6.3 Orchestrator

这是首版唯一流程控制中枢。

负责：

* 初始化根任务
* 调用 Planner
* 根据 Planner 输出创建执行任务
* 调用 Executor
* 调用 Reviewer
* 根据 Reviewer 结果决定通过、重试或失败
* 更新 state
* 写 event_log

必须具备的流程控制能力：

1. 创建根任务
2. 调用 Planner 生成执行任务与验收要求
3. 调用 Executor 生成产物
4. 调用 Reviewer 审核产物
5. Reviewer 通过则完成
6. Reviewer 驳回则重试
7. 超过 `retry_limit` 则 workflow failed

必须提供的能力：

* `run_workflow(task_id)`
* `invoke_role(role, task)`
* `handle_review_result(review_result, task)`
* `append_event(event)`

---

## 6.4 AgentRunner

负责：

* 按角色组装输入
* 调用 Mock LLM 或真实 LLM
* 返回结构化结果

首版默认只实现 Mock LLM 驱动的单次调用版本。

不允许实现：

* idle loop
* 常驻线程
* 自动唤醒
* 自治调度全局任务池

返回结构建议：

```json
{
  "status": "ok | failed",
  "summary": "string",
  "artifact_refs": ["string"],
  "next_action": "complete | retry | reject",
  "structured_output": {}
}
```

Planner / Executor / Reviewer 三类角色，至少需要有可区分的 mock 行为。

---

## 6.5 ToolSandbox

负责：

* 工具注册
* 参数校验
* 执行保护
* 异常标准化

要求：

* 任何工具异常都不能直接抛到主流程导致崩溃
* 必须转为 `status=failed` 的标准结果返回

必须提供：

* `@tool(...)`
* `execute_tool(tool_name, kwargs)`

---

## 6.6 AuditLog

负责：

* 将关键事件统一追加写入 `event_log.jsonl`

必须记录：

* workflow 启动
* task 创建
* task 开始
* task 完成
* task 失败
* reviewer pass
* reviewer reject
* tool failed
* workflow 完成
* workflow 失败

---

## 7. 失败模型必须统一实现

你必须实现以下失败语义，不允许各模块自行发明状态。

### 7.1 tool_failed

表示工具执行失败。

要求：

* 记录错误
* 返回标准化失败结果
* 不直接导致主线程崩溃

### 7.2 task_failed

表示单个任务执行失败或未达标。

要求：

* 写入 `failure_reason`
* 更新 task 状态
* 写入 event_log

### 7.3 workflow_failed

表示整个工作流终止失败。

要求：

* 写入 `state.last_error`
* 更新 `workflow_status=failed`
* 写入终止事件

### 7.4 aborted

表示人工或系统主动终止。

首版可预留状态，不要求完整实现人工中断逻辑。

---

## 8. 开发阶段与验收要求

你必须严格分 4 个阶段实现。

---

## 阶段 1：Workspace 与 Schema

### 本阶段目标

完成最基础的文件结构与数据模型能力。

### 允许实现

* 工作空间初始化
* JSON 原子写
* JSONL 追加写
* Task / State / Event schema 定义与校验

### 禁止实现

* Orchestrator 主流程
* AgentRunner
* 真实模型调用
* ToolSandbox 的复杂逻辑

### 必须通过的测试

* `test_workspace_init`
* `test_atomic_write`
* `test_append_jsonl`
* `test_task_schema_validation`
* `test_state_schema_validation`
* `test_event_schema_validation`

### 本阶段完成标准

满足以下条件才算完成：

* 能初始化标准目录
* 能原子写入 state/task 文件
* 能追加 event_log
* schema 校验测试全绿

---

## 阶段 2：TaskManager

### 本阶段目标

完成任务创建、选择、状态变更、依赖解除。

### 允许实现

* 创建任务
* 读取任务
* 获取下一个可执行任务
* 标记完成/失败
* 解除依赖

### 禁止实现

* 多 Agent 自治领取
* 并发 claim
* inbox 模型
* 守护循环

### 必须通过的测试

* `test_create_task`
* `test_get_next_runnable_task`
* `test_priority_order`
* `test_unblock_after_complete`
* `test_mark_task_failed`
* `test_record_failure_reason`

### 本阶段完成标准

满足以下条件才算完成：

* 能正确创建任务文件
* 能正确选出可执行任务
* 任务完成后能解除后续依赖
* 失败信息能落盘

---

## 阶段 3：Orchestrator + Mock Agent 闭环

### 本阶段目标

完成首版闭环工作流。

### 允许实现

* Mock Planner
* Mock Executor
* Mock Reviewer
* Orchestrator 主流程
* 审计日志记录
* 重试控制

### 禁止实现

* 真实大模型 API
* 自动上下文压缩
* 常驻 Agent
* 多工作流并发执行

### 必须通过的测试

* `test_planner_executor_reviewer_flow`
* `test_review_reject_and_retry`
* `test_workflow_fail_after_retry_limit`
* `test_event_log_complete_trace`
* `test_artifact_written_correctly`

### 本阶段完成标准

满足以下条件才算完成：

* 能从根任务进入规划阶段
* Planner 能生成执行任务
* Executor 能生成产物
* Reviewer 能通过或驳回
* 驳回后可按限制重试
* 超限后 workflow failed
* 所有关键事件写入 event_log

---

## 阶段 4：ToolSandbox + 真实模型接入（可选）

### 本阶段目标

在前 3 阶段稳定后，再接入工具执行与真实模型。

### 允许实现

* 工具注册
* 工具执行
* Provider 接口抽象
* 真实模型适配层

### 禁止实现

* 改写前 3 阶段已通过的核心行为
* 用真实模型替代 mock 测试基线

### 必须通过的测试

* `test_tool_success`
* `test_tool_failure_standardized`
* `test_provider_adapter_returns_standard_result`
* 前三阶段测试必须继续全绿

### 本阶段完成标准

满足以下条件才算完成：

* 工具异常不会打崩流程
* 模型 provider 返回统一结构
* mock 闭环能力不退化

---

## 9. 代码实现要求

### 9.1 基本要求

* Python 3 实现
* 代码必须可直接运行
* 所有核心函数必须有类型标注
* 必须有必要注释
* 不允许只写伪代码或空实现

### 9.2 错误处理要求

* 所有 I/O 必须有明确异常处理
* 所有工具调用必须有异常包装
* 不允许 silent failure
* 错误必须可追踪到 event_log 或 failure_reason

### 9.3 测试要求

* 使用 pytest
* 测试必须运行在临时目录
* 测试不能污染真实目录
* demo 不依赖外部网络

---

## 10. Mock LLM 行为要求

为保证闭环可测，你必须实现 Mock LLM。

最低要求如下：

### Planner Mock

输入复杂任务描述，返回：

* 拆解出的执行任务
* 验收要求
* 结构化任务清单

### Executor Mock

输入任务与上下文，返回：

* 产物内容
* 产物路径
* 执行摘要

### Reviewer Mock

输入执行结果，返回两种情况之一：

* pass
* reject + 修改意见

你必须支持“第一次 reject，第二次 pass”这类可控测试场景。

---

## 11. 你不能做的事情

以下行为视为偏离任务目标：

1. 一次性写出几千行未经测试的代码
2. 先接真实 API，再补 mock
3. 把系统写成多线程/多进程常驻服务
4. 引入 Redis、SQLite、消息队列作为首版默认依赖
5. 把 context compression 做成核心逻辑
6. 用自然语言摘要替代结构化状态
7. 省略 event_log
8. 省略 failure_reason
9. 忽略阶段测试直接进入下一阶段

---

## 12. 最终验收口径

只有满足以下条件，才算实现完成：

### 功能上

* 能跑通 Planner → Executor → Reviewer 的闭环
* 能处理 pass / reject / retry / fail
* 能落盘状态、任务、产物、日志
* 能在 mock 环境下重复稳定运行

### 工程上

* 核心模块职责清晰
* 数据结构完整
* 失败语义统一
* 测试分阶段通过
* event_log 可用于复盘

### 架构上

* 遵守半中心化控制
* 遵守单次调用型 Agent
* 遵守文件为状态真源
* 未越界实现首版之外的复杂能力

---

## 13. 建议输出顺序

你应按下面顺序输出开发结果，而不是一次性给出全部代码：

### 第 1 次输出

* schemas
* workspace_store
* 对应测试

### 第 2 次输出

* task_manager
* 对应测试

### 第 3 次输出

* mock agent_runner
* orchestrator
* audit_log
* 对应测试

### 第 4 次输出

* tool_sandbox
* provider adapter（可选）
* 最终 demo
* README

---

## 14. 一句话任务定义

实现一个**基于文件状态真源、由 Orchestrator 半中心化推进、支持 Planner/Executor/Reviewer 闭环、可由 AI coder 分阶段 TDD 完成的多 Agent 协同框架首版**。

---

如果你要，我下一步可以继续写“给 AI coder 的首轮编码提示词”。
