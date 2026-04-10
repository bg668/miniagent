from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Sequence

from .config import AgentLoopConfig, AgentOptions
from .errors import AgentAlreadyRunningError, InvalidContinuationError, ListenerOutsideRunError
from .events import AgentEndEvent, AgentEvent, AgentStartEvent, MessageEndEvent, MessageStartEvent, TurnEndEvent
from .loop import run_agent_loop, run_agent_loop_continue
from .models import AgentContext, AgentMessage, AssistantMessage, ImageContent, TextContent, TokenUsage, UserMessage
from .queues import PendingMessageQueue
from .run_control import CancelToken, RunHandle
from .state import AgentStateView, MutableAgentState


def _default_convert_to_llm(messages: Sequence[AgentMessage]) -> list[AgentMessage]:
    return [message for message in messages if message.role in {"user", "assistant", "toolResult"}]


async def _missing_stream_fn(model, context, config, cancel_token):
    raise RuntimeError("No stream_fn configured for Agent")


async def _maybe_await(value: Awaitable[Any] | Any) -> Any:
    if isawaitable(value):
        return await value
    return value


class Agent:
    def __init__(self, options: AgentOptions | None = None) -> None:
        options = options or AgentOptions()
        self._state = MutableAgentState(
            system_prompt=options.system_prompt,
            model=options.model,
            thinking_level=options.thinking_level,
            tools=options.tools,
            messages=options.messages,
        )
        self._listeners: list[Callable[[AgentEvent, CancelToken | None], Awaitable[None] | None]] = []
        self._steering_queue = PendingMessageQueue(options.steering_mode)
        self._follow_up_queue = PendingMessageQueue(options.follow_up_mode)
        self._active_run: RunHandle | None = None

        self.convert_to_llm = options.convert_to_llm or _default_convert_to_llm
        self.transform_context = options.transform_context
        self.stream_fn = options.stream_fn or _missing_stream_fn
        self.get_api_key = options.get_api_key
        self.before_tool_call = options.before_tool_call
        self.after_tool_call = options.after_tool_call
        self.on_payload = options.on_payload
        self.tool_execution = options.tool_execution
        self.session_id = options.session_id
        self.thinking_budgets = options.thinking_budgets
        self.max_retry_delay_ms = options.max_retry_delay_ms
        self.api_key = options.api_key
        self.base_url = options.base_url
        self.temperature = options.temperature
        self.top_p = options.top_p
        self.max_tokens = options.max_tokens
        self.metadata = dict(options.metadata)

    @property
    def state(self) -> AgentStateView:
        return self._state.snapshot()

    def subscribe(self, listener: Callable[[AgentEvent, CancelToken | None], Awaitable[None] | None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return _unsubscribe

    def steer(self, message: AgentMessage) -> None:
        self._steering_queue.enqueue(message)

    def follow_up(self, message: AgentMessage) -> None:
        self._follow_up_queue.enqueue(message)

    def abort(self) -> None:
        if self._active_run is not None:
            self._active_run.cancel()

    async def wait_for_idle(self) -> None:
        if self._active_run is None:
            return
        await self._active_run.wait_idle()

    def reset(self) -> None:
        self._state.messages = []
        self._state.reset_runtime_fields()
        self._steering_queue.clear()
        self._follow_up_queue.clear()

    async def prompt(self, input_value: str | AgentMessage | list[AgentMessage], images: list[ImageContent] | None = None) -> None:
        if self._active_run is not None:
            raise AgentAlreadyRunningError(
                "Agent is already processing a prompt. Use steer() or follow_up() to queue messages, or wait for completion."
            )
        prompt_messages = self._normalize_prompt_input(input_value, images)
        await self._run_prompt_messages(prompt_messages)

    async def continue_(self) -> None:
        if self._active_run is not None:
            raise AgentAlreadyRunningError("Agent is already processing. Wait for completion before continuing.")

        last_message = self._state.messages[-1] if self._state.messages else None
        if last_message is None:
            raise InvalidContinuationError("no messages to continue from")

        if last_message.role == "assistant":
            steering = self._steering_queue.drain()
            if steering:
                await self._run_prompt_messages(steering, skip_initial_steering_poll=True)
                return

            followups = self._follow_up_queue.drain()
            if followups:
                await self._run_prompt_messages(followups, skip_initial_steering_poll=False)
                return

            raise InvalidContinuationError("cannot continue from assistant")

        await self._run_continuation()

    def _normalize_prompt_input(
        self,
        input_value: str | AgentMessage | list[AgentMessage],
        images: list[ImageContent] | None = None,
    ) -> list[AgentMessage]:
        if isinstance(input_value, list):
            return list(input_value)

        if not isinstance(input_value, str):
            return [input_value]

        content: list[TextContent | ImageContent] = [TextContent(text=input_value)]
        if images:
            content.extend(images)
        return [UserMessage(content=content)]

    def _create_context_snapshot(self) -> AgentContext:
        return AgentContext(
            system_prompt=self._state.system_prompt,
            messages=list(self._state.messages),
            tools=list(self._state.tools),
        )

    def _create_loop_config(self, *, skip_initial_steering_poll: bool = False) -> AgentLoopConfig:
        first_steering_poll = skip_initial_steering_poll

        async def get_steering_messages() -> list[AgentMessage]:
            nonlocal first_steering_poll
            if first_steering_poll:
                first_steering_poll = False
                return []
            return self._steering_queue.drain()

        async def get_followup_messages() -> list[AgentMessage]:
            return self._follow_up_queue.drain()

        return AgentLoopConfig(
            model=self._state.model,
            stream_fn=self.stream_fn,
            convert_to_llm=self.convert_to_llm,
            transform_context=self.transform_context,
            get_api_key=self.get_api_key,
            get_steering_messages=get_steering_messages,
            get_followup_messages=get_followup_messages,
            tool_execution=self.tool_execution,
            before_tool_call=self.before_tool_call,
            after_tool_call=self.after_tool_call,
            on_payload=self.on_payload,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            session_id=self.session_id,
            thinking_level=self._state.thinking_level,
            thinking_budgets=self.thinking_budgets,
            metadata=dict(self.metadata),
        )

    async def _run_prompt_messages(self, messages: list[AgentMessage], *, skip_initial_steering_poll: bool = False) -> None:
        async def _executor(cancel_token: CancelToken) -> None:
            await self._process_event(AgentStartEvent())
            await run_agent_loop(
                prompts=messages,
                context=self._create_context_snapshot(),
                config=self._create_loop_config(skip_initial_steering_poll=skip_initial_steering_poll),
                emit=self._process_event,
                cancel_token=cancel_token,
            )

        await self._run_with_lifecycle(_executor)

    async def _run_continuation(self) -> None:
        async def _executor(cancel_token: CancelToken) -> None:
            await self._process_event(AgentStartEvent())
            await run_agent_loop_continue(
                context=self._create_context_snapshot(),
                config=self._create_loop_config(),
                emit=self._process_event,
                cancel_token=cancel_token,
            )

        await self._run_with_lifecycle(_executor)

    async def _run_with_lifecycle(self, executor: Callable[[CancelToken], Awaitable[None]]) -> None:
        if self._active_run is not None:
            raise AgentAlreadyRunningError("Agent is already processing.")

        self._active_run = RunHandle.create()
        self._state.is_streaming = True
        self._state.streaming_message = None
        self._state.error_message = None

        try:
            await executor(self._active_run.cancel_token)
        except Exception as exc:
            await self._handle_run_failure(exc, self._active_run.cancel_token.is_cancelled())
        finally:
            self._finish_run()

    async def _handle_run_failure(self, error: Exception, aborted: bool) -> None:
        failure_message = AssistantMessage(
            content=[TextContent(text="")],
            api=self._state.model.api,
            provider=self._state.model.provider,
            model=self._state.model.id,
            usage=TokenUsage(),
            stop_reason="aborted" if aborted else "error",
            error_message=str(error),
        )
        await self._process_event(MessageStartEvent(message=failure_message))
        await self._process_event(MessageEndEvent(message=failure_message))
        await self._process_event(TurnEndEvent(message=failure_message, tool_results=[]))
        await self._process_event(AgentEndEvent(messages=[failure_message]))

    def _finish_run(self) -> None:
        self._state.is_streaming = False
        self._state.streaming_message = None
        self._state.pending_tool_calls = set()
        if self._active_run is not None:
            self._active_run.mark_idle()
        self._active_run = None

    async def _process_event(self, event: AgentEvent) -> None:
        if event.type == "message_start":
            self._state.streaming_message = event.message
        elif event.type == "message_update":
            self._state.streaming_message = event.message
        elif event.type == "message_end":
            self._state.streaming_message = None
            self._state.messages.append(event.message)
        elif event.type == "tool_execution_start":
            pending = set(self._state.pending_tool_calls)
            pending.add(event.tool_call_id)
            self._state.pending_tool_calls = pending
        elif event.type == "tool_execution_end":
            pending = set(self._state.pending_tool_calls)
            pending.discard(event.tool_call_id)
            self._state.pending_tool_calls = pending
        elif event.type == "turn_end":
            if isinstance(event.message, AssistantMessage) and event.message.error_message:
                self._state.error_message = event.message.error_message
        elif event.type == "agent_end":
            self._state.streaming_message = None

        if self._active_run is None:
            raise ListenerOutsideRunError("Agent listener invoked outside active run")
        for listener in list(self._listeners):
            await _maybe_await(listener(event, self._active_run.cancel_token))


__all__ = [
    "Agent",
]
