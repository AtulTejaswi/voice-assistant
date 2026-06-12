# Extending the Assistant with New Commands

You can add new commands **without touching the core or guard logic**.

## Method 1: Add a rule to the interpreter

Edit `src/command_interpreter.py` and call `self.register()` in `load_defaults()`:

```python
self.register(r"minimize (all )?windows", "minimize_windows", self._handle_minimize)
```

Then add a handler method:

```python
@staticmethod
def _handle_minimize(cmd: Command) -> str:
    return cmd
```

Then wire it in `src/action_executor.py`:

```python
def minimize_windows(self) -> str:
    pyautogui.hotkey("win", "d")
    return "Minimized all windows"
```

And add to the dispatch table in `main.py`:

```python
"minimize_windows": lambda _: self.executor.minimize_windows(),
```

## Method 2: Commands plugin system

Drop a `.py` file into the `commands/` folder with a `register(interpreter, executor)` function.
The assistant will auto-discover and load it on startup (planned feature).

## Security

- The **credential guard** runs on every transcription before any handler is invoked.
- You cannot bypass the guard from within a command handler — it checks before dispatch.
- If your command needs user-provided text, the full text is still guard-checked.
