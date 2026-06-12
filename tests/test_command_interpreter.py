"""
Tests for the CommandInterpreter module.
"""

import pytest
from src.command_interpreter import CommandInterpreter, Command


@pytest.fixture
def interpreter():
    ci = CommandInterpreter()
    ci.load_defaults()
    return ci


def test_open_app(interpreter: CommandInterpreter):
    result = interpreter.interpret("open Chrome")
    assert result is not None
    cmd, _ = result
    assert cmd.action == "open_app"
    assert cmd.target.lower() == "chrome"


def test_open_app_with_launch(interpreter: CommandInterpreter):
    result = interpreter.interpret("launch Notepad")
    assert result is not None
    assert result[0].action == "open_app"


def test_type_text(interpreter: CommandInterpreter):
    result = interpreter.interpret("type hello world")
    assert result is not None
    cmd, _ = result
    assert cmd.action == "type_text"
    assert cmd.text == "hello world"


def test_press_key(interpreter: CommandInterpreter):
    result = interpreter.interpret("press enter")
    assert result is not None
    assert result[0].action == "press_key"
    assert result[0].target == "enter"


def test_create_file(interpreter: CommandInterpreter):
    result = interpreter.interpret("create file called notes.txt")
    assert result is not None
    assert result[0].action == "create_file"


def test_search_web(interpreter: CommandInterpreter):
    result = interpreter.interpret("search for python tutorials")
    assert result is not None
    assert result[0].action == "search_web"


def test_open_url(interpreter: CommandInterpreter):
    result = interpreter.interpret("go to github.com")
    assert result is not None
    assert result[0].action == "open_url"


def test_tell_time(interpreter: CommandInterpreter):
    result = interpreter.interpret("what time is it")
    assert result is not None
    assert result[0].action == "tell_time"


def test_tell_date(interpreter: CommandInterpreter):
    result = interpreter.interpret("what is the date today")
    assert result is not None
    assert result[0].action == "tell_date"


def test_media_play_pause(interpreter: CommandInterpreter):
    result = interpreter.interpret("play media")
    assert result is not None
    assert result[0].action == "media_play_pause"


def test_volume_up(interpreter: CommandInterpreter):
    result = interpreter.interpret("volume up")
    assert result is not None
    assert result[0].action == "volume"


def test_lock_pc(interpreter: CommandInterpreter):
    result = interpreter.interpret("lock my computer")
    assert result is not None
    assert result[0].action == "lock_pc"


def test_screenshot(interpreter: CommandInterpreter):
    result = interpreter.interpret("take screenshot")
    assert result is not None
    assert result[0].action == "screenshot"


def test_unrecognized_command(interpreter: CommandInterpreter):
    result = interpreter.interpret("do something crazy that I never registered")
    assert result is None


def test_case_insensitivity(interpreter: CommandInterpreter):
    result = interpreter.interpret("OPEN FIREFOX")
    assert result is not None
    assert result[0].action == "open_app"
