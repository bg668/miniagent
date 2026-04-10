

from miniagent.core.llm import BaseLLM
from miniagent.core.agent import BaseAgent

class PlanAndSolveAgent(BaseAgent):
    def __init__(self, agent_id: str, llm, tool_registry) -> None:
        super().__init__(agent_id, llm, tool_registry)
        pass

    def run_loop(self, task_input: str):
        pass
