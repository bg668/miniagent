import json
import os
from pathlib import Path
from time import time

from miniagent.core.llm import BaseLLM
from miniagent.core.agent import BaseAgent
from miniagent.tools.todo import TodoManager

TOKEN_THRESHOLD = 100000

WORKDIR = Path.cwd()
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TASKS_DIR = WORKDIR / ".tasks"
SKILLS_DIR = WORKDIR / "skills"
MODEL = os.environ["SUMMARY_MODEL"]
MODEL_API_KEY = os.environ["SUMMARY_MODEL_API_KEY"]
summary_model = BaseLLM(model=MODEL, api_key=MODEL_API_KEY)


def microcompact_anthropic(messages: list):
    indices = []
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    indices.append(part)
    
    if len(indices) <= 3:
        return
    for part in indices[:-3]:
        if isinstance(part.get("content"), str) and len(part["content"]) > 100:
            part["content"] = "[cleared]"

def microcompact(messages: list):
    """
    tool message example:
    {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "name": "query_edr", 
        "content": "{\"status\": \"clean\", \"logs\": \"...\"}" 
    }
    """
    tool_messages_index = []
    # 1. 收集所有 role 为 "tool" 的顶层消息引用
    for i, msg in enumerate(messages):
        if msg.get("role") == "tool":
            tool_messages_index.append(i)
            
    # 2. 如果工具结果数量小于等于 3，跳过压缩
    if len(tool_messages_index) <= 3:
        return
        
    # 3. 对除了最近 3 条之外的旧工具结果进行截断
    for msg_index in tool_messages_index[:-3]:
        content = messages[msg_index].get("content")
        # OpenAI 的 tool message content 通常是字符串
        if isinstance(content, str) and len(content) > 100:
            messages[msg_index]["content"] = "[cleared]"

    return

def estimate_tokens(messages: list) -> int:
    return len(json.dumps(messages, default=str)) // 4

def auto_compact(messages: list, client:BaseLLM) -> list:
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    conv_text = json.dumps(messages, default=str)[-80000:]
    resp = client.generate(
        messages=[{"role": "user", "content": f"Summarize for continuity:\n{conv_text}"}]
    )
    summary = resp.content[0].text
    return [
        {"role": "user", "content": f"[Compressed. Transcript: {path}]\n{summary}"},
    ]




TODO = TodoManager()

TOOL_HANDLERS = {
    "TodoWrite":        lambda **kw: TODO.update(kw["items"]),
}


class ReActAgent(BaseAgent):
    def __init__(self, agent_id: str, llm, tools) -> None:
        super().__init__(agent_id, llm, tools)
        
        self.messages = []
        pass

    
    def run_loop(self, task_input: str):
        loop_meta = {"step":0, "rounds_without_todo":0}
        self.messages = [{"role": "user", "content": task_input}]


        while True:
            # 1. 触发pre 处理机制
            self._before_llm_call(loop_meta)
            # 2. 带着环境感知调用 LLM
            response = self.llm.generate(
                messages=self.messages, 
                tools=self.tools
            )

            message = response.choices[0].message
            self.messages.append(message)

            has_tool_call = (
                response.choices[0].finish_reason == "tool_calls"
                or bool(getattr(message, "tool_calls", None))
            )

            # 3. 处理工具调用
            if has_tool_call:
                self._after_llm_call(response, loop_meta)
                continue

            # 4. 没有工具调用，认为是最终答案
            else:
                final_answer = response.choices[0].message.content
                break

        result = {
            "final_answer": final_answer,
            "messages": self.messages
        }

        return result


    def _before_llm_call(self, loop_meta):
        # 1. 压缩上下文
        """
        1.1 微压缩：清理过长的工具返回结果替换为[cleared]，保留最近的3条
        1.2 大幅压缩：
            - 将历史信息保存到本地，交给llm按照后续可继续执行进行总结，得到总结结果
            - 清空上下文，总结结果以用户消息的形式加入上下文
        """
        microcompact(self.messages)
        if estimate_tokens(self.messages) > TOKEN_THRESHOLD:
            print("[ReActAgent] Context tokens exceed threshold, performing compression...")
            # 将历史信息保存到本地
            
        return
    

    def _after_llm_call(self, response, loop_meta):
        
        used_todo_currently = False
        for tool_call in response.tool_calls:
            handler = TOOL_HANDLERS.get(tool_call.name)
            try:
                tool_input = dict(tool_call.arguments or {})
                tool_input["tool_use_id"] = tool_call.id
                output = handler(**tool_input) if handler else f"Unknown tool: {tool_call.name}"
            except Exception as e:
                output = f"Error: {e}"
            print(f"> {tool_call.name}: {str(output)[:200]}")
            # 将工具调用结果以工具消息的形式加入上下文，供后续模型使用
            self.messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_call.name,
                "content": str(output),
            })

            # 特殊工具结果处理
            # todo处理：设置没有执行 todo 次数为 0
            if tool_call.name == "todo":
                loop_meta['use_todo'] = True
                loop_meta['rounds_without_todo'] = 0
                used_todo_currently = True
            
    
        # 没有执行 todo，计数器加1
        if not used_todo_currently:
            loop_meta['rounds_without_todo'] += 1


        return 


