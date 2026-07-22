"""
Tests for color_shell.py: ColorShell/PrintShell wrapping helpers and the
Spinner terminal-progress helper.

Tests exercise the *logic* (which color constant gets applied, state
transitions of the Spinner, what text ends up written to the stream)
rather than asserting on hardcoded ANSI escape sequences -- comparisons
are made against the module's own named color constants.
"""

import io
import time

import pytest

from linuxmusterTools.common.color_shell import (
    ColorShell,
    PrintShell,
    Spinner,
    SHELL_COLOR_WARNING,
    SHELL_COLOR_SUCCESS,
    SHELL_COLOR_ALERT,
    SHELL_COLOR_DANGER,
    SHELL_COLOR_INFO,
    SHELL_COLOR_LINUXMUSTER,
    SHELL_COLOR_ENDC,
)


# --- ColorShell -------------------------------------------------------------

@pytest.mark.parametrize("method_name, color_const", [
    ("red", SHELL_COLOR_DANGER),
    ("orange", SHELL_COLOR_ALERT),
    ("yellow", SHELL_COLOR_WARNING),
    ("blue", SHELL_COLOR_INFO),
    ("green", SHELL_COLOR_SUCCESS),
    ("lmn", SHELL_COLOR_LINUXMUSTER),
])
def test_color_shell_methods_wrap_text_in_their_color(method_name, color_const):
    shell = ColorShell()
    method = getattr(shell, method_name)

    result = method("hello")

    assert result == f"{color_const}hello{SHELL_COLOR_ENDC}"


def test_color_shell_private_color_helper_is_generic():
    shell = ColorShell()
    assert shell._color("\033[1m", "text") == "\033[1mtext\033[0m"


# --- PrintShell --------------------------------------------------------------

def test_printsh_prints_colorized_text_with_given_end(capsys):
    shell = PrintShell()

    shell.printsh(SHELL_COLOR_INFO, "hello", end="")

    captured = capsys.readouterr()
    assert captured.out == f"{SHELL_COLOR_INFO}hello{SHELL_COLOR_ENDC}"


@pytest.mark.parametrize("method_name, color_const", [
    ("danger", SHELL_COLOR_DANGER),
    ("alert", SHELL_COLOR_ALERT),
    ("warning", SHELL_COLOR_WARNING),
    ("info", SHELL_COLOR_INFO),
    ("success", SHELL_COLOR_SUCCESS),
    ("lmn", SHELL_COLOR_LINUXMUSTER),
])
def test_printshell_convenience_methods_use_correct_color(capsys, method_name, color_const):
    shell = PrintShell()
    method = getattr(shell, method_name)

    method("hi there")

    captured = capsys.readouterr()
    assert captured.out == f"{color_const}hi there{SHELL_COLOR_ENDC}\n"


def test_printshell_convenience_methods_respect_custom_end(capsys):
    shell = PrintShell()

    shell.danger("hi", end="")

    captured = capsys.readouterr()
    assert captured.out == f"{SHELL_COLOR_DANGER}hi{SHELL_COLOR_ENDC}"


# --- Spinner -----------------------------------------------------------------

class FakeTTYStream(io.StringIO):
    """A StringIO that reports itself as a TTY, so Spinner.start() spawns
    its animation thread."""

    def isatty(self):
        return True


class FakeNonTTYStream(io.StringIO):
    def isatty(self):
        return False


def test_spinner_initial_state():
    spinner = Spinner()

    assert spinner.stop_running is None
    assert spinner.spin_thread is None
    assert spinner.text == ""
    assert spinner.last_text == ""
    assert spinner.update is False


def test_spinner_print_updates_text_and_marks_update_pending():
    spinner = Spinner()

    spinner.print("step one")

    assert spinner.text == "step one"
    assert spinner.last_text == ""
    assert spinner.update is True

    spinner.print("step two")

    assert spinner.text == "step two"
    assert spinner.last_text == "step one"


def test_spinner_start_is_a_no_op_when_stdout_is_not_a_tty(monkeypatch):
    fake_stream = FakeNonTTYStream()
    monkeypatch.setattr("linuxmusterTools.common.color_shell.sys.stdout", fake_stream)

    spinner = Spinner()
    spinner.start()

    # No thread spawned, nothing written (no cursor-hide sequence).
    assert spinner.spin_thread is None
    assert fake_stream.getvalue() == ""

    # stop() is safe to call even though start() never actually started.
    spinner.stop()


def test_spinner_start_and_stop_spawn_and_join_thread_on_tty(monkeypatch):
    fake_stream = FakeTTYStream()
    monkeypatch.setattr("linuxmusterTools.common.color_shell.sys.stdout", fake_stream)

    spinner = Spinner()
    spinner.start()

    assert spinner.spin_thread is not None
    assert spinner.spin_thread.is_alive()

    spinner.print("working")
    # Give the busy-loop a brief moment to pick up the pending update.
    time.sleep(0.05)

    spinner.stop()

    assert spinner.spin_thread.is_alive() is False

    output = fake_stream.getvalue()
    # Cursor is hidden on start and restored on stop.
    assert "\033[?25l" in output
    assert "\033[?25h" in output
    # The spinner text that was set via print() made it into the stream.
    assert "working" in output


def test_spinner_context_manager_starts_and_stops(monkeypatch):
    fake_stream = FakeTTYStream()
    monkeypatch.setattr("linuxmusterTools.common.color_shell.sys.stdout", fake_stream)

    with Spinner() as spinner:
        spinner.print("doing stuff")
        time.sleep(0.05)

    # __exit__ stops the thread and writes a final checkmark line with the
    # last text that was set.
    assert spinner.spin_thread.is_alive() is False
    output = fake_stream.getvalue()
    assert SHELL_COLOR_SUCCESS in output
    assert "doing stuff" in output


def test_spinner_context_manager_does_not_suppress_exceptions(monkeypatch):
    fake_stream = FakeTTYStream()
    monkeypatch.setattr("linuxmusterTools.common.color_shell.sys.stdout", fake_stream)

    with pytest.raises(ValueError):
        with Spinner():
            raise ValueError("boom")
