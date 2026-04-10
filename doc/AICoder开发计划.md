# Agent SDK AICoder 开发计划

## 0. 执行约束

本计划面向 AICoder 执行，不面向人类排期讨论。执行时必须遵守以下硬约束：

1. 以 `doc/概要设计.md` 和 `doc/详细设计.md` 为唯一设计基线，行为语义优先于实现简化。
2. 以 `refs/agent.ts`、`refs/agent-loop.ts`、`refs/types.ts` 为参考语义源；实现方式应尽量符合 Python 习惯，例如使用 `dataclass`、`Protocol`、`asyncio` 和只读视图，但对外可观察语义不得偏离参考实现，尤其不能改变事件顺序、消息落地顺序、取消收敛方式或 `continue_()` 边界。
3. 本轮只实现 OpenAI 风格 `chat.completions` 适配，不实现 `refs/proxy.ts`、不实现多 provider、不过度抽象 transport。
4. 技能、计划任务、长期记忆、业务工具编排都不进入 `agent_sdk` 内核，只通过扩展点接入。
5. 每个任务完成后必须补测试；没有测试的实现视为未完成。
6. 不允许跳步实现。必须先稳定类型和事件模型，再实现 loop、adapter、工具执行和 Agent 外观层。

## 1. 目标产物

完成一个可运行的 Python SDK，目录如下：

```text
agent_sdk/
├── __init__.py
├── adapters/
│   ├── __init__.py
│   └── openai_chatcompletions.py
├── runtime/
│   ├── __init__.py
│   ├── agent.py
│   ├── config.py
│   ├── errors.py
│   ├── events.py
│   ├── loop.py
│   ├── models.py
│   ├── queues.py
│   ├── run_control.py
│   ├── state.py
│   ├── stream_handler.py
│   └── tool_executor.py
└── tests/
    ├── __init__.py
    ├── test_agent_lifecycle.py
    ├── test_continue_semantics.py
    ├── test_openai_adapter.py
    ├── test_stream_handler.py
    ├── test_tool_executor_parallel.py
    └── test_tool_executor_sequential.py
```

## 2. 全局完成定义

只有同时满足以下条件，整个开发任务才算完成：

1. `Agent` 暴露 `prompt()`、`continue_()`、`abort()`、`wait_for_idle()`、`steer()`、`follow_up()`、`subscribe()`、`reset()`。
2. 外部可读取稳定状态快照：`messages`、`is_streaming`、`streaming_message`、`pending_tool_calls`、`error_message`、`model`、`system_prompt`、`tools`。
3. 支持 stream 与 non-stream 的 OpenAI `chat.completions`，且在 runtime 内通过统一接口收敛。
4. 支持顺序与并行两种工具执行模式，并保持“准备顺序稳定、执行可并发、结果落地顺序稳定”。
5. 取消能在模型流、工具执行、hook、事件监听等待边界生效，并收敛为协议内 `aborted` 或 `error`。
6. 测试覆盖生命周期、continue 语义、流收敛、工具顺序、并行工具顺序、OpenAI adapter 映射。

## 3. 执行顺序

严格按以下阶段执行；未完成前一阶段，不得进入后一阶段。

### Phase 1: 搭建 Runtime 类型底座

目标：先把所有后续模块依赖的公共类型定死，避免 loop 和 adapter 反复返工。

输入：
- `doc/概要设计.md`
- `doc/详细设计.md`
- `refs/types.ts`

输出文件：
- `agent_sdk/__init__.py`
- `agent_sdk/runtime/__init__.py`
- `agent_sdk/runtime/models.py`
- `agent_sdk/runtime/events.py`
- `agent_sdk/runtime/errors.py`
- `agent_sdk/runtime/config.py`

必须实现：
- 定义消息模型：`UserMessage`、`AssistantMessage`、`ToolResultMessage`
- 定义内容块：`TextContent`、`ImageContent`、`ThinkingContent`、`ToolCallContent`
- 定义 `AgentToolResult`、`AgentContext`、`AgentTool`
- 定义 `ThinkingLevel`、`ToolExecutionMode`
- 定义事件 dataclass：`agent_start`、`agent_end`、`turn_start`、`turn_end`、`message_start`、`message_update`、`message_end`、`tool_execution_start`、`tool_execution_update`、`tool_execution_end`
- 定义配置对象：`AgentOptions`、`AgentLoopConfig`、`BeforeToolCallContext`、`BeforeToolCallResult`、`AfterToolCallContext`、`AfterToolCallResult`
- 定义异常：`AgentRuntimeError`、`AgentAlreadyRunningError`、`InvalidContinuationError`、`ListenerOutsideRunError`、`ToolPreparationError`、`OpenAIAdapterError`

实现约束：
- 使用 `dataclass`、`Protocol`、`Literal`、`Enum` 或等价 typing 工具，避免裸字典。
- 字段命名优先贴近 Python 风格，但关键语义字段必须与设计文档一一对应。
- `AssistantMessage` 必须包含 `stop_reason`、`error_message`、`usage`、`provider`、`model`、`api`、`timestamp`。
- `ToolResultMessage` 必须包含 `tool_call_id`、`tool_name`、`content`、`details`、`is_error`。

完成定义：
- 后续模块不需要再定义新的核心消息/事件结构。
- 类型层可以独立被 import，不产生循环依赖。

验证：
- 新增或运行 `agent_sdk/tests` 中的基础导入测试。
- 运行静态检查或至少执行一次 `python -m compileall agent_sdk`。

### Phase 2: 状态、队列、运行控制

目标：实现可观察状态和统一取消机制，为 loop 和 Agent 外观层提供基础设施。

输入：
- Phase 1 产物
- `refs/agent.ts`

输出文件：
- `agent_sdk/runtime/state.py`
- `agent_sdk/runtime/queues.py`
- `agent_sdk/runtime/run_control.py`

必须实现：
- `MutableAgentState`
- `AgentStateView`
- `PendingMessageQueue`
- `CancelToken`
- `RunHandle`

实现约束：
- `AgentStateView` 对外只读；列表、集合必须返回副本或不可变视图。
- `PendingMessageQueue` 必须支持 `all` 和 `one-at-a-time` 两种 `drain` 语义。
- 取消信号必须统一由 `CancelToken` 表达；不得在不同模块混用布尔标记和 `task.cancel()` 直杀。

完成定义：
- 状态层可以在没有 Agent 的情况下独立单测。
- 队列行为能准确复现 steering / follow-up 的差异。

验证：
- 编写队列和取消控制的单元测试。

### Phase 3: 先实现 Stream Handler，再接 OpenAI Adapter

目标：统一 stream / non-stream 的 runtime 入口，避免 loop 分叉。

输入：
- Phase 1-2 产物
- `doc/详细设计.md` 中 `stream_assistant_response()` 伪代码
- `refs/agent-loop.ts`

输出文件：
- `agent_sdk/runtime/stream_handler.py`
- `agent_sdk/adapters/__init__.py`
- `agent_sdk/adapters/openai_chatcompletions.py`
- `agent_sdk/tests/test_stream_handler.py`
- `agent_sdk/tests/test_openai_adapter.py`

必须实现：
- runtime 侧统一的 assistant 响应流接口
- partial assistant message 的生成、更新、最终收敛
- OpenAI non-stream 响应到 final message 的映射
- OpenAI stream chunk 到 runtime 事件流的映射

实现约束：
- runtime 内只保留一条主路径：`stream_assistant_response(...)`。
- non-stream 适配必须包装成可被统一消费的“简化事件流”，不能在 loop 内写 `if stream else` 双逻辑。
- partial assistant message 在上下文中必须表现为“最后一条 assistant 快照持续更新”，而不是每个 delta 一条消息。
- adapter 层只做协议映射，不直接管理 transcript、队列或 Agent 状态。

完成定义：
- `stream_handler` 在 mock stream 和 mock non-stream 上都能返回同一种 final assistant message。
- 测试能断言 `message_start -> message_update* -> message_end` 的事件序列。

验证：
- 运行 `test_stream_handler.py`
- 运行 `test_openai_adapter.py`

### Phase 4: 工具执行链路

目标：实现“准备、校验、hook、执行、后处理、结果落地”的全链路，并保证并行语义严格对齐。

输入：
- Phase 1-3 产物
- `refs/agent-loop.ts`
- `doc/详细设计.md` 中工具执行伪代码

输出文件：
- `agent_sdk/runtime/tool_executor.py`
- `agent_sdk/tests/test_tool_executor_sequential.py`
- `agent_sdk/tests/test_tool_executor_parallel.py`

必须实现：
- `execute_tool_calls()`
- `prepare_tool_call()`
- 顺序执行路径
- 并行执行路径
- `before_tool_call` / `after_tool_call`
- 工具执行中 update 事件透传
- 找不到工具、参数校验失败、hook 阻断、执行异常时的错误 tool result 收敛

实现约束：
- 并行模式下仅执行阶段允许并发。
- 结果落地顺序必须与 assistant message 中的 tool call 顺序一致，不得按完成先后写入。
- 工具失败不允许炸穿 loop，必须转换成 `ToolResultMessage(is_error=True)`。
- 所有 hook 和 execute 都必须接收同一个 `CancelToken`。

完成定义：
- 顺序模式可逐个断言事件序列。
- 并行模式可验证执行实际并发，但 transcript 顺序稳定。

验证：
- 运行 `test_tool_executor_sequential.py`
- 运行 `test_tool_executor_parallel.py`

### Phase 5: 主循环

目标：落地双层 loop，并把 steering、follow-up、tool-call continuation、abort 收敛到统一运行模型。

输入：
- Phase 1-4 产物
- `refs/agent-loop.ts`
- `doc/详细设计.md` 中 `run_loop()` 伪代码

输出文件：
- `agent_sdk/runtime/loop.py`

必须实现：
- `run_agent_loop()`
- `run_agent_loop_continue()`
- `run_loop()`

实现约束：
- 保留双层循环，不得合并成单层 while。
- `agent_start`、`turn_start`、`message_start`/`message_end`、assistant 收敛、tool 执行、`turn_end`、`agent_end` 的顺序必须稳定。
- 当前 turn 执行完成后先拉 steering，再在将要结束时拉 follow-up。
- assistant 若以 `error` 或 `aborted` 收敛，必须终止运行并发出 `agent_end`。

完成定义：
- loop 模块不直接持有 Agent 内部状态，只通过 `emit` 回调输出事件。
- 单独测试 loop 时可用 fake emit + fake stream_fn 验证语义。

验证：
- 为 loop 新增回归测试，或在生命周期测试中覆盖其关键分支。

### Phase 6: Agent 外观层

目标：提供对外稳定 SDK 接口，封装 lifecycle、状态归约、监听器、等待 idle 和 reset。

输入：
- Phase 1-5 产物
- `refs/agent.ts`

输出文件：
- `agent_sdk/runtime/agent.py`
- `agent_sdk/tests/test_agent_lifecycle.py`
- `agent_sdk/tests/test_continue_semantics.py`
- `agent_sdk/__init__.py`

必须实现：
- `Agent.prompt()`
- `Agent.continue_()`
- `Agent.abort()`
- `Agent.wait_for_idle()`
- `Agent.steer()`
- `Agent.follow_up()`
- `Agent.subscribe()`
- `Agent.reset()`
- 事件归约到公开状态

实现约束：
- 同时只允许一个 active run。
- `wait_for_idle()` 等待的不只是主循环退出，还包括监听器执行完成。
- `continue_()` 语义必须严格按设计文档处理 assistant 结尾时的 steering / follow-up / error 分支。
- `reset()` 只清 transcript、错误态和队列，不重置模型、system_prompt、tools。

完成定义：
- 外部仅通过 `Agent` 就能驱动整个 SDK。
- 生命周期测试覆盖 prompt -> tool -> follow-up -> idle 和 abort -> prompt -> continue 的组合路径。

验证：
- 运行 `test_agent_lifecycle.py`
- 运行 `test_continue_semantics.py`

### Phase 7: 收口与回归

目标：清理导出面、补漏测试、确认与设计范围一致，不引入超范围能力。

输入：
- 全部前序产物

输出文件：
- 必要时补充 `agent_sdk/tests/__init__.py`
- 必要时补充包级导出

必须实现：
- 清理未使用接口
- 明确包导出面
- 补充缺失测试
- 补充最小 smoke test

实现约束：
- 不因为“方便后续扩展”而加多 provider、proxy、memory、scheduler 等未授权能力。
- 不把技能系统或任务计划器塞进 `agent_sdk`。

完成定义：
- 测试集全绿。
- `python -m compileall agent_sdk` 通过。
- 代码目录与详细设计基本一致。

## 4. AICoder 任务卡模板

后续拆子任务时，统一使用以下格式，不要写成泛泛的“建议”：

```text
Task: <唯一任务名>
Goal: <本任务唯一目标>
Inputs:
- <文档/参考代码/已完成模块>
Write Scope:
- <允许修改的文件>
Do:
- <必须完成的实现项>
Do Not:
- <明确禁止做的事>
Done When:
- <可验证的完成条件>
Verify:
- <命令或测试名>
```

## 5. 建议的首批任务拆分

以下是建议直接喂给 AICoder 的首批任务，不是给人类看的里程碑描述。

### Task 01

```text
Task: bootstrap-runtime-types
Goal: 建立 runtime 的消息、事件、配置、错误类型底座
Inputs:
- doc/概要设计.md
- doc/详细设计.md
- refs/types.ts
Write Scope:
- agent_sdk/__init__.py
- agent_sdk/runtime/__init__.py
- agent_sdk/runtime/models.py
- agent_sdk/runtime/events.py
- agent_sdk/runtime/config.py
- agent_sdk/runtime/errors.py
Do:
- 定义所有核心 dataclass / Protocol / Literal
- 保证 AssistantMessage 和 ToolResultMessage 字段完整
- 保证事件类型可被后续状态归约直接消费
Do Not:
- 不实现 Agent、loop、adapter、tool executor
- 不引入业务层概念
Done When:
- 后续模块可以只 import 这些类型而不再自定义核心结构
Verify:
- python -m compileall agent_sdk
```

### Task 02

```text
Task: implement-state-and-run-control
Goal: 实现只读状态视图、消息队列和统一取消控制
Inputs:
- Task 01 产物
- refs/agent.ts
Write Scope:
- agent_sdk/runtime/state.py
- agent_sdk/runtime/queues.py
- agent_sdk/runtime/run_control.py
Do:
- 实现 MutableAgentState / AgentStateView / PendingMessageQueue / CancelToken / RunHandle
- 提供 all 与 one-at-a-time 两种 drain 语义
Do Not:
- 不在此任务中实现 Agent 对外 API
Done When:
- 状态和队列可独立测试
Verify:
- python -m compileall agent_sdk
```

### Task 03

```text
Task: implement-stream-handler-and-openai-adapter
Goal: 建立统一 assistant 响应流接口，并完成 OpenAI chat.completions 适配
Inputs:
- Task 01-02 产物
- refs/agent-loop.ts
- doc/详细设计.md
Write Scope:
- agent_sdk/runtime/stream_handler.py
- agent_sdk/adapters/__init__.py
- agent_sdk/adapters/openai_chatcompletions.py
- agent_sdk/tests/test_stream_handler.py
- agent_sdk/tests/test_openai_adapter.py
Do:
- 统一处理 stream / non-stream
- 实现 partial assistant message 收敛
- 用测试固定事件时序
Do Not:
- 不实现多 provider
- 不让 adapter 管状态
Done When:
- stream 和 non-stream 都能通过统一接口产出 final assistant message
Verify:
- pytest agent_sdk/tests/test_stream_handler.py agent_sdk/tests/test_openai_adapter.py
```

### Task 04

```text
Task: implement-tool-executor
Goal: 实现工具调用顺序模式和并行模式
Inputs:
- Task 01-03 产物
- refs/agent-loop.ts
- doc/详细设计.md
Write Scope:
- agent_sdk/runtime/tool_executor.py
- agent_sdk/tests/test_tool_executor_sequential.py
- agent_sdk/tests/test_tool_executor_parallel.py
Do:
- 实现 prepare / validate / before hook / execute / after hook / finalize 全链路
- 保证并行模式结果顺序稳定
Do Not:
- 不按完成先后写 transcript
- 不让工具异常炸穿 loop
Done When:
- 顺序与并行语义都被测试固定
Verify:
- pytest agent_sdk/tests/test_tool_executor_sequential.py agent_sdk/tests/test_tool_executor_parallel.py
```

### Task 05

```text
Task: implement-loop-and-agent
Goal: 完成双层 loop 和 Agent 外观层
Inputs:
- Task 01-04 产物
- refs/agent.ts
- refs/agent-loop.ts
- doc/详细设计.md
Write Scope:
- agent_sdk/runtime/loop.py
- agent_sdk/runtime/agent.py
- agent_sdk/tests/test_agent_lifecycle.py
- agent_sdk/tests/test_continue_semantics.py
- agent_sdk/__init__.py
Do:
- 实现 prompt / continue_ / abort / wait_for_idle / steer / follow_up / subscribe / reset
- 实现事件归约与 active run 管理
- 固定 continue 语义与 abort 收敛语义
Do Not:
- 不新增未设计能力
- 不绕过 emit 直接在 loop 中写 Agent 状态
Done When:
- 生命周期与 continue 语义测试通过
Verify:
- pytest agent_sdk/tests/test_agent_lifecycle.py agent_sdk/tests/test_continue_semantics.py
```

## 6. 禁止 AICoder 自行扩展的内容

以下内容全部视为超范围，即使“顺手实现”也不允许：

1. `refs/proxy.ts` 对应协议。
2. Anthropic、Gemini、Azure 或其他 provider adapter。
3. 内置技能系统、任务计划器、长期记忆或持久化。
4. 数据库、缓存层、HTTP 服务层、CLI 层。
5. 与设计文档不一致的“更优雅”事件模型。

## 7. 最终验收命令

若仓库补齐了测试依赖，最终验收至少执行：

```bash
python -m compileall agent_sdk
pytest agent_sdk/tests
```

如果测试环境尚未建立，AICoder 至少必须保证：

```bash
python -m compileall agent_sdk
```
