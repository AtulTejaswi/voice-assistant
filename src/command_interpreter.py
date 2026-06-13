"""
Command interpreter — LLM-based intent parsing.

Replaced the old regex system with an LLM reasoning core.
The LLM receives the transcript + conversation history + tool schemas
and decides what to do: respond directly or call a tool.
"""

from src.llm_core import LLMCore
from src.action_executor import ActionExecutor


class CommandInterpreter:
    def __init__(self, llm: LLMCore, executor: ActionExecutor):
        self._llm = llm
        self._executor = executor
        self._setup_tools()

    def _setup_tools(self):
        # Load skill tools
        try:
            from src import skills
            skills.register_skills(self._executor)
        except Exception as e:
            print(f"[Skills] Load error: {e}")

        schemas = self._executor.tool_schemas()
        handlers = self._executor.get_handlers()
        self._llm.register_tools_from_dict(schemas, handlers)

    def interpret(self, text: str) -> tuple[bool, str]:
        """
        Process user input through the LLM.

        Returns (success, response_string).
        success=True means the LLM understood and acted on the input.
        response_string is the LLM's text response (already spoken-suitable).
        """
        response = self._llm.reason(text)
        return (True, response)

    def interpret_stream(self, text: str):
        """Streaming version — yields response tokens."""
        return self._llm.reason_stream(text)

    def add_to_history(self, role: str, content: str):
        self._llm.add_message(role, content)

    def clear_history(self):
        self._llm.clear_history()
