from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal, Sequence, TypeAlias

from .models import AgentMessage, AgentToolResult, AssistantMessage, AssistantMessageEvent, ToolResultMessage

if TYPE_CHECKING:
    from .run_control import CancelToken


@dataclass(slots=True)
class AgentStartEvent:
    type: Literal["agent_start"] = field(init=False, default="agent_start")


@dataclass(slots=True)
class AgentEndEvent:
    messages: Sequence[AgentMessage]
    type: Literal["agent_end"] = field(init=False, default="agent_end")


@dataclass(slots=True)
class TurnStartEvent:
    type: Literal["turn_start"] = field(init=False, default="turn_start")


@dataclass(slots=True)
class TurnEndEvent:
    message: AgentMessage
    tool_results: Sequence[ToolResultMessage]
    type: Literal["turn_end"] = field(init=False, default="turn_end")


@dataclass(slots=True)
class MessageStartEvent:
    message: AgentMessage
    type: Literal["message_start"] = field(init=False, default="message_start")


@dataclass(slots=True)
class MessageUpdateEvent:
    message: AssistantMessage
    assistant_message_event: AssistantMessageEvent
    type: Literal["message_update"] = field(init=False, default="message_update")


@dataclass(slots=True)
class MessageEndEvent:
    message: AgentMessage
    type: Literal["message_end"] = field(init=False, default="message_end")


@dataclass(slots=True)
class ToolExecutionStartEvent:
    tool_call_id: str
    tool_name: str
    args: Any
    type: Literal["tool_execution_start"] = field(init=False, default="tool_execution_start")


@dataclass(slots=True)
class ToolExecutionUpdateEvent:
    tool_call_id: str
    tool_name: str
    args: Any
    partial_result: AgentToolResult
    type: Literal["tool_execution_update"] = field(init=False, default="tool_execution_update")


@dataclass(slots=True)
class ToolExecutionEndEvent:
    tool_call_id: str
    tool_name: str
    result: AgentToolResult
    is_error: bool
    type: Literal["tool_execution_end"] = field(init=False, default="tool_execution_end")


AgentEvent: TypeAlias = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
)
AgentEventListener: TypeAlias = Callable[[AgentEvent, "CancelToken | None"], Awaitable[None] | None]


__all__ = [
    "AgentEndEvent",
    "AgentEvent",
    "AgentEventListener",
    "AgentStartEvent",
    "MessageEndEvent",
    "MessageStartEvent",
    "MessageUpdateEvent",
    "ToolExecutionEndEvent",
    "ToolExecutionStartEvent",
    "ToolExecutionUpdateEvent",
    "TurnEndEvent",
    "TurnStartEvent",
]
