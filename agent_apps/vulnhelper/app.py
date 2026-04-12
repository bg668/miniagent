from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .bootstrap import build_app
from .config import build_default_config


class ThinkingStreamPrinter:
    def __init__(self) -> None:
        self._active_phase: str | None = None
        self._printed_any = False

    def reset(self) -> None:
        self._active_phase = None
        self._printed_any = False

    def on_agent_event(self, phase: str, event, _cancel_token) -> None:
        if getattr(event, "type", None) != "message_update":
            return
        assistant_event = getattr(event, "assistant_message_event", None)
        if assistant_event is None or getattr(assistant_event, "type", None) != "thinking_delta":
            return
        delta = getattr(assistant_event, "delta", "")
        if not delta:
            return

        if self._active_phase != phase:
            if self._printed_any:
                print()
            print(f"[Thinking:{phase}] ", end="", flush=True)
            self._active_phase = phase
            self._printed_any = True

        print(delta, end="", flush=True)

    def finish(self) -> None:
        if self._printed_any:
            print()
        self.reset()


def _load_runtime_config():
    load_dotenv()
    config = build_default_config()
    if not config.config_json_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config.config_json_path}")
    return config


def _humanize_state(state: str) -> str:
    mapping = {
        "idle": "空闲",
        "waiting_for_confirmation": "等待确认",
        "executing_query": "执行查询",
        "report_ready": "报告已生成",
        "drilldown_ready": "下钻结果已生成",
        "failed": "失败",
    }
    return mapping.get(state, state)


def _print_startup_banner(config_path: Path, model_id: str, base_url: str | None, session_id: str) -> None:
    print("✓ 已加载配置:", config_path.name)
    print("✓ 使用模型:", model_id)
    print("✓ Base URL:", base_url or "默认")
    print("✓ Session ID:", session_id)
    print()
    print("=" * 50)
    print("VulnHelper CLI")
    print("输入 'exit' 或 'quit' 退出")
    print("=" * 50)


def _print_output(output) -> None:
    print(f"[状态] {_humanize_state(output.state)} ({output.state})")
    print(output.markdown)


async def main() -> None:
    try:
        config = _load_runtime_config()
    except (FileNotFoundError, ValueError) as exc:
        print(f"✗ 错误: {exc}")
        return
    missing_profiles = config.missing_api_key_profile_refs()
    if missing_profiles:
        joined = ", ".join(missing_profiles)
        print(f"✗ 错误: 以下 provider profile 未读取到 API Key: {joined}")
        return

    app = build_app(config)
    session_id = str(uuid4())
    thinking_printer = ThinkingStreamPrinter()
    unsubscribe = app.subscribe_agent_events(thinking_printer.on_agent_event)

    _print_startup_banner(config.config_json_path, config.planner_model.id, config.base_url, session_id)

    try:
        if len(sys.argv) > 1:
            for text in sys.argv[1:]:
                print(f"\n👤 你: {text}")
                print("\n🤖 VulnHelper:")
                thinking_printer.reset()
                try:
                    output = await app.handle_text(session_id=session_id, text=text)
                    thinking_printer.finish()
                    _print_output(output)
                except Exception as exc:
                    thinking_printer.finish()
                    print(f"[异常: {exc}]")
            return

        while True:
            try:
                text = input("\n👤 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 再见！")
                break

            if text.lower() in {"exit", "quit", "退出"}:
                print("\n👋 再见！")
                break
            if not text:
                continue

            print("\n🤖 VulnHelper:")
            thinking_printer.reset()
            try:
                output = await app.handle_text(session_id=session_id, text=text)
                thinking_printer.finish()
                _print_output(output)
            except Exception as exc:
                thinking_printer.finish()
                print(f"[异常: {exc}]")
    finally:
        unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
