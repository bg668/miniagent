from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .config import (
    UNSET,
    AfterToolCallContext,
    AgentLoopConfig,
    BeforeToolCallContext,
)
from .events import (
    AgentEvent,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
)
from .models import AgentContext, AgentTool, AgentToolResult, AssistantMessage, TextContent, ToolCallContent, ToolResultMessage
from .run_control import CancelToken


AgentEventSink = Callable[[AgentEvent], Awaitable[None] | None]


@dataclass(slots=True)
class PreparedToolCall:
    tool_call: ToolCallContent
    tool: AgentTool[Any, Any]
    args: Any


@dataclass(slots=True)
class ImmediateToolOutcome:
    result: AgentToolResult
    is_error: bool


@dataclass(slots=True)
class ExecutedToolCallOutcome:
    result: AgentToolResult
    is_error: bool


async def _maybe_await(value: Awaitable[Any] | Any) -> Any:
    if isawaitable(value):
        return await value
    return value


def _validate_schema_value(schema: Mapping[str, Any], value: Any, path: str = "args") -> None:
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        required = schema.get("required", []) or []
        for key in required:
            if key not in value:
                raise ValueError(f"{path}.{key} is required")
        properties = schema.get("properties", {}) or {}
        additional_properties = schema.get("additionalProperties", True)
        for key, item in value.items():
            property_schema = properties.get(key)
            if property_schema is not None:
                _validate_schema_value(property_schema, item, f"{path}.{key}")
            elif additional_properties is False:
                raise ValueError(f"{path}.{key} is not allowed")
        return

    if expected_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema_value(item_schema, item, f"{path}[{index}]")
        return

    primitive_checks = {
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected_type in primitive_checks and not primitive_checks[expected_type](value):
        raise ValueError(f"{path} must be of type {expected_type}")


def validate_tool_arguments(tool: AgentTool[Any, Any], tool_call: ToolCallContent) -> Any:
    schema = getattr(tool, "input_schema", None)
    args = tool_call.arguments
    if schema is None:
        return args
    if not isinstance(schema, Mapping):
        raise ValueError(f"Tool {tool.name} input_schema must be a mapping")
    _validate_schema_value(schema, args)
    return args


def find_tool(tools: Sequence[AgentTool[Any, Any]] | None, tool_name: str) -> AgentTool[Any, Any] | None:
    if tools is None:
        return None
    for tool in tools:
        if tool.name == tool_name:
            return tool
    return None


def create_error_tool_result(message: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=message)], details={})


def _maybe_prepare_arguments(tool: AgentTool[Any, Any], tool_call: ToolCallContent) -> ToolCallContent:
    prepare_arguments = getattr(tool, "prepare_arguments", None)
    if prepare_arguments is None:
        return tool_call

    prepared_arguments = prepare_arguments(tool_call.arguments)
    if prepared_arguments is tool_call.arguments:
        return tool_call
    return ToolCallContent(id=tool_call.id, name=tool_call.name, arguments=prepared_arguments)


async def prepare_tool_call(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_call: ToolCallContent,
    config: AgentLoopConfig,
    emit: AgentEventSink | None = None,
    cancel_token: CancelToken | None = None,
) -> PreparedToolCall | ImmediateToolOutcome:
    del emit
    if cancel_token is not None:
        cancel_token.raise_if_cancelled()

    tool = find_tool(current_context.tools, tool_call.name)
    if tool is None:
        return ImmediateToolOutcome(
            result=create_error_tool_result(f"Tool {tool_call.name} not found"),
            is_error=True,
        )

    try:
        prepared_call = _maybe_prepare_arguments(tool, tool_call)
        validated_args = validate_tool_arguments(tool, prepared_call)

        if config.before_tool_call is not None:
            before_result = await _maybe_await(
                config.before_tool_call(
                    BeforeToolCallContext(
                        assistant_message=assistant_message,
                        tool_call=tool_call,
                        args=validated_args,
                        context=current_context,
                    ),
                    cancel_token,
                )
            )
            if before_result is not None and before_result.block:
                return ImmediateToolOutcome(
                    result=create_error_tool_result(before_result.reason or "Tool execution was blocked"),
                    is_error=True,
                )

        return PreparedToolCall(tool_call=tool_call, tool=tool, args=validated_args)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return ImmediateToolOutcome(result=create_error_tool_result(str(exc)), is_error=True)


async def execute_prepared_tool_call(
    prepared: PreparedToolCall,
    emit: AgentEventSink,
    cancel_token: CancelToken | None = None,
) -> ExecutedToolCallOutcome:
    if cancel_token is not None:
        cancel_token.raise_if_cancelled()

    update_tasks: list[asyncio.Task[None]] = []

    async def _emit_update(partial_result: AgentToolResult) -> None:
        await _maybe_await(
            emit(
                ToolExecutionUpdateEvent(
                    tool_call_id=prepared.tool_call.id,
                    tool_name=prepared.tool_call.name,
                    args=prepared.tool_call.arguments,
                    partial_result=partial_result,
                )
            )
        )

    def on_update(partial_result: AgentToolResult) -> None:
        update_tasks.append(asyncio.create_task(_emit_update(partial_result)))

    try:
        result = await prepared.tool.execute(
            prepared.tool_call.id,
            prepared.args,
            cancel_token,
            on_update,
        )
        if update_tasks:
            await asyncio.gather(*update_tasks)
        return ExecutedToolCallOutcome(result=result, is_error=False)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if update_tasks:
            await asyncio.gather(*update_tasks)
        return ExecutedToolCallOutcome(
            result=create_error_tool_result(str(exc)),
            is_error=True,
        )


async def emit_tool_call_outcome(
    tool_call: ToolCallContent,
    result: AgentToolResult,
    is_error: bool,
    emit: AgentEventSink,
) -> ToolResultMessage:
    await _maybe_await(
        emit(
            ToolExecutionEndEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=result,
                is_error=is_error,
            )
        )
    )

    tool_result_message = ToolResultMessage(
        tool_call_id=tool_call.id,
        tool_name=tool_call.name,
        content=deepcopy(result.content),
        details=deepcopy(result.details),
        is_error=is_error,
    )
    await _maybe_await(emit(MessageStartEvent(message=tool_result_message)))
    await _maybe_await(emit(MessageEndEvent(message=tool_result_message)))
    return tool_result_message


async def finalize_executed_tool_call(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    prepared: PreparedToolCall,
    executed: ExecutedToolCallOutcome,
    config: AgentLoopConfig,
    emit: AgentEventSink,
    cancel_token: CancelToken | None = None,
) -> ToolResultMessage:
    if cancel_token is not None:
        cancel_token.raise_if_cancelled()

    result = executed.result
    is_error = executed.is_error

    if config.after_tool_call is not None:
        after_result = await _maybe_await(
            config.after_tool_call(
                AfterToolCallContext(
                    assistant_message=assistant_message,
                    tool_call=prepared.tool_call,
                    args=prepared.args,
                    result=result,
                    is_error=is_error,
                    context=current_context,
                ),
                cancel_token,
            )
        )
        if after_result is not None:
            result = AgentToolResult(
                content=result.content if after_result.content is UNSET else (after_result.content or []),
                details=result.details if after_result.details is UNSET else after_result.details,
            )
            is_error = is_error if after_result.is_error is UNSET else bool(after_result.is_error)

    return await emit_tool_call_outcome(prepared.tool_call, result, is_error, emit)


async def execute_tool_calls_sequential(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_calls: Sequence[ToolCallContent],
    config: AgentLoopConfig,
    emit: AgentEventSink,
    cancel_token: CancelToken | None = None,
) -> list[ToolResultMessage]:
    results: list[ToolResultMessage] = []

    for tool_call in tool_calls:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

        await _maybe_await(
            emit(
                ToolExecutionStartEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                )
            )
        )
        preparation = await prepare_tool_call(
            current_context=current_context,
            assistant_message=assistant_message,
            tool_call=tool_call,
            config=config,
            emit=emit,
            cancel_token=cancel_token,
        )

        if isinstance(preparation, ImmediateToolOutcome):
            results.append(await emit_tool_call_outcome(tool_call, preparation.result, preparation.is_error, emit))
            continue

        executed = await execute_prepared_tool_call(preparation, emit, cancel_token)
        results.append(
            await finalize_executed_tool_call(
                current_context=current_context,
                assistant_message=assistant_message,
                prepared=preparation,
                executed=executed,
                config=config,
                emit=emit,
                cancel_token=cancel_token,
            )
        )

    return results


async def execute_tool_calls_parallel(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_calls: Sequence[ToolCallContent],
    config: AgentLoopConfig,
    emit: AgentEventSink,
    cancel_token: CancelToken | None = None,
) -> list[ToolResultMessage]:
    prepared_items: list[PreparedToolCall | ImmediateToolOutcome] = []
    execution_tasks: dict[int, asyncio.Task[ExecutedToolCallOutcome]] = {}

    for index, tool_call in enumerate(tool_calls):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

        await _maybe_await(
            emit(
                ToolExecutionStartEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                )
            )
        )
        preparation = await prepare_tool_call(
            current_context=current_context,
            assistant_message=assistant_message,
            tool_call=tool_call,
            config=config,
            emit=emit,
            cancel_token=cancel_token,
        )
        prepared_items.append(preparation)

        if isinstance(preparation, PreparedToolCall):
            execution_tasks[index] = asyncio.create_task(execute_prepared_tool_call(preparation, emit, cancel_token))

    results: list[ToolResultMessage] = []
    for index, preparation in enumerate(prepared_items):
        if isinstance(preparation, ImmediateToolOutcome):
            tool_call = tool_calls[index]
            results.append(await emit_tool_call_outcome(tool_call, preparation.result, preparation.is_error, emit))
            continue

        executed = await execution_tasks[index]
        results.append(
            await finalize_executed_tool_call(
                current_context=current_context,
                assistant_message=assistant_message,
                prepared=preparation,
                executed=executed,
                config=config,
                emit=emit,
                cancel_token=cancel_token,
            )
        )

    return results


async def execute_tool_calls(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    config: AgentLoopConfig,
    emit: AgentEventSink,
    cancel_token: CancelToken | None = None,
) -> list[ToolResultMessage]:
    tool_calls = [item for item in assistant_message.content if isinstance(item, ToolCallContent)]
    if config.tool_execution.value == "sequential":
        return await execute_tool_calls_sequential(
            current_context=current_context,
            assistant_message=assistant_message,
            tool_calls=tool_calls,
            config=config,
            emit=emit,
            cancel_token=cancel_token,
        )
    return await execute_tool_calls_parallel(
        current_context=current_context,
        assistant_message=assistant_message,
        tool_calls=tool_calls,
        config=config,
        emit=emit,
        cancel_token=cancel_token,
    )


__all__ = [
    "AgentEventSink",
    "ExecutedToolCallOutcome",
    "ImmediateToolOutcome",
    "PreparedToolCall",
    "create_error_tool_result",
    "emit_tool_call_outcome",
    "execute_prepared_tool_call",
    "execute_tool_calls",
    "execute_tool_calls_parallel",
    "execute_tool_calls_sequential",
    "finalize_executed_tool_call",
    "find_tool",
    "prepare_tool_call",
    "validate_tool_arguments",
]
