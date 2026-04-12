from __future__ import annotations

from ..agentsdk import TextContent, ThinkingContent


def extract_latest_assistant_text(messages) -> str:
    for message in reversed(list(messages)):
        if getattr(message, "role", None) != "assistant":
            continue
        texts = [block.text for block in message.content if isinstance(block, TextContent)]
        if texts:
            return "\n".join(texts).strip()
    return ""


def extract_assistant_thinking(messages, start_index: int = 0) -> str | None:
    parts: list[str] = []
    for message in list(messages)[start_index:]:
        if getattr(message, "role", None) != "assistant":
            continue
        thinking_blocks = [block.thinking.strip() for block in message.content if isinstance(block, ThinkingContent) and block.thinking.strip()]
        if thinking_blocks:
            parts.append("\n".join(thinking_blocks))
    merged = "\n\n".join(part for part in parts if part).strip()
    return merged or None
