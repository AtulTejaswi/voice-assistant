"""
LLM Reasoning Core — Ollama client with tool-calling support.

Replaces the regex command interpreter with an LLM that:
1. Receives user transcript + conversation history + tool schemas
2. Decides whether to respond directly or call a tool
3. Returns structured output for execution
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import requests

SYSTEM_PROMPT = """You are JARVIS — a local voice-controlled AI assistant on Windows.

You are efficient, warm, and have a dry wit. Keep responses concise (1-3 sentences).

RULES:
- If the user asks to DO something (open, type, search, lock, volume, screenshot, etc.), call the right tool.
- If the user is just chatting (hello, how are you, etc.), respond naturally — DO NOT call any tool.
- If the user asks a question, answer from your knowledge — DO NOT call a tool unless it requires real-time info (time, date).
- Never handle passwords, API keys, or credentials.
- After a tool runs, summarize the result briefly.
"""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., str]


class LLMCore:
    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        system_prompt: str = SYSTEM_PROMPT,
        max_history: int = 20,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._system_prompt = system_prompt
        self._max_history = max_history
        self._tools: dict[str, ToolSpec] = {}
        self._history: list[dict[str, str]] = []
        self._user_name: Optional[str] = None

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., str],
    ):
        self._tools[name] = ToolSpec(name, description, parameters, handler)

    def register_tools_from_dict(self, tool_defs: dict[str, dict[str, Any]], handlers: dict[str, Callable]):
        for name, defn in tool_defs.items():
            self.register_tool(
                name=defn["name"],
                description=defn["description"],
                parameters=defn["parameters"],
                handler=handlers[name],
            )

    @property
    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str):
        self._history.append({"role": role, "content": content})
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def clear_history(self):
        self._history = []

    # ------------------------------------------------------------------
    # Core reasoning
    # ------------------------------------------------------------------

    def reason(self, user_input: str) -> str:
        return self._chat(user_input)

    def _chat(self, user_input: str, include_tools: bool = True) -> str:
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._history)
        if user_input.strip():
            messages.append({"role": "user", "content": user_input})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        if include_tools and self._tools:
            payload["tools"] = self.tool_specs

        resp = requests.post(
            f"{self._base_url}/v1/chat/completions",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "")

        # Handle tool calls
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            self.add_message("user", user_input)
            self.add_message("assistant", content or f"[Calling tools: {[tc['function']['name'] for tc in tool_calls]}]")

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                result = self._execute_tool(fn_name, fn_args)
                self.add_message("tool", result)

            # Get final response (no tools this time — model just summarizes)
            return self._chat("What happened?", include_tools=False)

        # Plain text response
        final = content.strip() or "I'm not sure how to respond to that."
        self.add_message("user", user_input)
        self.add_message("assistant", final)
        return final

    def reason_stream(self, user_input: str):
        """Streaming version — yields tokens as they arrive."""
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if self._tools:
            payload["tools"] = self.tool_specs

        with requests.post(
            f"{self._base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            full_content = ""
            tool_calls = None

            for line in resp.iter_lines():
                if not line or line.startswith(b":"):
                    continue
                data_str = line.decode("utf-8").removeprefix("data: ").strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    token = delta["content"]
                    full_content += token
                    yield token

                if delta.get("tool_calls"):
                    tool_calls = delta["tool_calls"]

            if tool_calls:
                self.add_message("user", user_input)
                self.add_message("assistant", full_content or json.dumps(tool_calls))
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    result = self._execute_tool(fn_name, fn_args)
                    self.add_message("tool", result)
                # Recurse for final text
                for token in self.reason_stream(""):
                    yield token
            else:
                self.add_message("user", user_input)
                self.add_message("assistant", full_content)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            result = tool.handler(**args)
            return str(result)
        except Exception as e:
            return f"Error executing {name}: {e}"

    # ------------------------------------------------------------------
    # User identity
    # ------------------------------------------------------------------

    def set_user_name(self, name: str):
        self._user_name = name
        self._system_prompt = SYSTEM_PROMPT.replace("the user", name)
