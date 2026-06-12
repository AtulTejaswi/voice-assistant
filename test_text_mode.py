"""
Text-mode test for the JARVIS LLM assistant.
Type commands to test the pipeline without needing a microphone.
"""
import sys
sys.path.insert(0, "A:/JARVIS/voice-assistant")

from src.credential_guard import CredentialGuard
from src.command_interpreter import CommandInterpreter
from src.action_executor import ActionExecutor
from src.llm_core import LLMCore

guard = CredentialGuard()
executor = ActionExecutor()
llm = LLMCore(model="llama3.2:3b")
interpreter = CommandInterpreter(llm, executor)

print("JARVIS Text Test Mode")
print("Type a command or 'quit' to exit.")
print()

while True:
    try:
        text = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not text:
        continue
    if text.lower() in ("quit", "exit"):
        break

    # Guard
    guard_result = guard.inspect(text)
    if not guard_result.safe:
        print(f"[Guard] BLOCKED: {guard_result.reason}")
        continue

    # LLM
    success, response = interpreter.interpret(text)
    if success:
        print(f"JARVIS: {response}")
    else:
        print(f"JARVIS: Sorry, I couldn't process that.")

    print()
