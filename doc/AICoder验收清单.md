# 二、AI coder 自验收清单

用途：给 AI coder 在交付前自查。
目标：尽量把“人工看出来的问题”提前在自检阶段发现。

---

## 1. 架构自检

### 1.1 控制权

* [ ] 是否只有 Orchestrator 推进主流程
* [ ] Agent 是否没有扫描全局任务池
* [ ] Agent 是否没有 claim_task 行为
* [ ] 是否没有实现常驻 idle loop

### 1.2 状态真源

* [ ] `state.json` 是否真实写入
* [ ] `tasks/*.json` 是否真实写入
* [ ] `artifacts/*` 是否真实写入
* [ ] `event_log.jsonl` 是否真实写入
* [ ] 是否没有依赖内存变量作为唯一状态来源

### 1.3 首版范围

* [ ] 是否没有 `.team/inbox/`
* [ ] 是否没有 Redis / SQLite 作为默认核心依赖
* [ ] 是否没有自动记忆压缩
* [ ] 是否没有多进程并发调度
* [ ] 是否没有分布式逻辑

---

## 2. 数据结构自检

### 2.1 Task

* [ ] Task 是否包含 `role`
* [ ] Task 是否包含 `blockedBy`
* [ ] Task 是否包含 `input_refs`
* [ ] Task 是否包含 `output_refs`
* [ ] Task 是否包含 `retry_count`
* [ ] Task 是否包含 `failure_reason`
* [ ] Task 是否包含 `priority`
* [ ] Task 是否包含 `created_at`
* [ ] Task 是否包含 `updated_at`

### 2.2 State

* [ ] State 是否包含 `workflow_status`
* [ ] State 是否包含 `current_task_id`
* [ ] State 是否包含 `current_role`
* [ ] State 是否包含 `retry_limit`
* [ ] State 是否包含 `review_round`
* [ ] State 是否包含 `last_error`

### 2.3 Event

* [ ] Event 是否包含 `kind`
* [ ] Event 是否包含 `type`
* [ ] Event 是否包含 `task_id`
* [ ] Event 是否包含 `summary`
* [ ] Event 是否包含 `details.error`
* [ ] Event 是否包含 `details.artifact_refs`

---

## 3. 模块职责自检

### 3.1 WorkspaceStore

* [ ] 是否只负责文件操作
* [ ] 核心状态文件覆盖写是否使用 `.tmp + fsync + os.replace`
* [ ] 是否没有掺入流程逻辑

### 3.2 TaskManager

* [ ] 是否只负责任务管理
* [ ] `get_next_runnable_task()` 是否只返回 `pending && blockedBy=[]`
* [ ] 是否支持按 `priority + created_at` 选任务
* [ ] `mark_task_completed()` 是否能解除依赖
* [ ] `mark_task_failed()` 是否会写入 `failure_reason`

### 3.3 Orchestrator

* [ ] 是否负责 Planner → Executor → Reviewer 主流程
* [ ] 是否处理 pass / reject / retry / fail
* [ ] 是否更新 `state.json`
* [ ] 是否写 `event_log.jsonl`

### 3.4 AgentRunner

* [ ] 是否为单次调用模式
* [ ] 是否没有轮询
* [ ] 是否没有全局调度
* [ ] 返回值是否为结构化结果

### 3.5 ToolSandbox

* [ ] 是否支持工具注册
* [ ] 是否统一标准化返回
* [ ] 工具异常是否不会打崩主流程

---

## 4. 工作流行为自检

### 4.1 标准路径

* [ ] 是否能从根任务进入 planning
* [ ] Planner 是否会输出执行任务
* [ ] Executor 是否会生成 artifact
* [ ] Reviewer 是否能输出 pass
* [ ] pass 后 workflow 是否进入 completed

### 4.2 驳回路径

* [ ] Reviewer 是否能输出 reject
* [ ] reject 后是否会触发重试
* [ ] `retry_count` 是否递增
* [ ] `review_round` 是否递增
* [ ] 是否重新进入 execution / review

### 4.3 失败路径

* [ ] 超过 `retry_limit` 后 workflow 是否进入 failed
* [ ] `state.last_error` 是否被填写
* [ ] 是否写入 workflow failed event

---

## 5. 审计与恢复自检

### 5.1 event_log

* [ ] 是否记录 workflow start
* [ ] 是否记录 task create
* [ ] 是否记录 task start
* [ ] 是否记录 task complete
* [ ] 是否记录 reviewer pass
* [ ] 是否记录 reviewer reject
* [ ] 是否记录 task fail
* [ ] 是否记录 workflow complete / failed

### 5.2 可复盘性

* [ ] 仅查看 workspace 目录，是否能看懂任务如何推进
* [ ] 仅查看 state + tasks + artifacts + event_log，是否能还原闭环过程

---

## 6. 失败模型自检

* [ ] 是否区分 `tool_failed`
* [ ] 是否区分 `task_failed`
* [ ] 是否区分 `workflow_failed`
* [ ] task 失败时是否写 `failure_reason`
* [ ] workflow 失败时是否写 `last_error`
* [ ] 失败是否只追加记录而不覆盖历史

---

## 7. 测试自检

### 7.1 阶段 1

* [ ] `test_workspace_init` 是否通过
* [ ] `test_atomic_write` 是否通过
* [ ] `test_append_jsonl` 是否通过
* [ ] schema 校验测试是否通过

### 7.2 阶段 2

* [ ] `test_create_task` 是否通过
* [ ] `test_get_next_runnable_task` 是否通过
* [ ] `test_priority_order` 是否通过
* [ ] `test_unblock_after_complete` 是否通过
* [ ] `test_mark_task_failed` 是否通过

### 7.3 阶段 3

* [ ] `test_planner_executor_reviewer_flow` 是否通过
* [ ] `test_review_reject_and_retry` 是否通过
* [ ] `test_workflow_fail_after_retry_limit` 是否通过
* [ ] `test_event_log_complete_trace` 是否通过
* [ ] `test_artifact_written_correctly` 是否通过

### 7.4 阶段 4

* [ ] `test_tool_success` 是否通过
* [ ] `test_tool_failure_standardized` 是否通过
* [ ] provider adapter 测试是否通过
* [ ] 前三阶段测试是否仍然全绿

---

## 8. 交付前最后自问

* [ ] 这套实现是否仍然是“首版框架”，而不是被我写成了复杂平台
* [ ] 这套实现是否真的可以让人只看文件就理解流程
* [ ] 这套实现是否真的把失败与重试做成了结构化状态
* [ ] 这套实现是否可以稳定重复跑通 mock demo
* [ ] 这套实现是否可以被后续替换存储后端、模型后端、工具后端

---

## 9. AI coder 自验收结论模板

### 可提交

* 所有阶段测试通过
* 主流程闭环通过
* 状态落盘完整
* 日志完整
* 首版边界未越界

### 不应提交

* 还有测试未通过
* 主流程只能跑 happy path
* reject / retry / fail 路径未验证
* 状态未完整落盘
* 架构偏离设计