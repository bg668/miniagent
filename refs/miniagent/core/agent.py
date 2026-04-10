"""Agent基类"""

from abc import ABC, abstractmethod
from typing import Optional
from unicodedata import name


class BaseAgent(ABC):
    def __init__(self, agent_id:str, llm, tools) -> None:
        
        self.agent_id = agent_id
        self.llm = llm
        self.tools = tools

    @abstractmethod
    def run_loop(self, input: str) -> str:
        """
        Agent的主循环逻辑，接收输入并返回输出
        子类必须实现具体的认知循环逻辑，如思考、决策、行动等。
        """
        pass

    def _before_llm_call(self, *args, **kwargs):
        """
        LLM调用前的预处理逻辑
        例如：日志记录、输入规范化、工具调用准备等。
        """
        pass

    def _after_llm_call(self, response):
        """
        LLM调用后的后处理逻辑
        例如：日志记录、响应解析、内存更新等。
        """
        pass


