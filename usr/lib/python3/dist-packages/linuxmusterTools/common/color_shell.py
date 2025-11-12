import itertools
import sys
import threading
import time


SHELL_COLOR_WARNING = '\033[93m'
SHELL_COLOR_SUCCESS = '\033[92m'
SHELL_COLOR_ALERT = '\033[38;5;208m'
SHELL_COLOR_DANGER = '\033[91m'
SHELL_COLOR_INFO = '\033[96m'
SHELL_COLOR_LINUXMUSTER = '\033[1m\033[38;5;214m'
SHELL_COLOR_ENDC = '\033[0m'
# For more definitions, see : https://misc.flogisoft.com/bash/tip_colors_and_formatting


class ColorShell:

    def _color(self, color, text):
        return f'{color}{text}{SHELL_COLOR_ENDC}'

    def red(self, text):
        return self._color(text, SHELL_COLOR_DANGER)

    def orange(self, text):
        return self._color(text, SHELL_COLOR_ALERT)

    def yellow(self, text):
        return self._color(text, SHELL_COLOR_WARNING)

    def blue(self, text):
        return self._color(text, SHELL_COLOR_INFO)

    def green(self, text):
        return self._color(text, SHELL_COLOR_SUCCESS)

    def lmn(self, text):
        return self._color(text, SHELL_COLOR_LINUXMUSTER)


class PrintShell:

    def __init__(self):
        self.color_shell = ColorShell()
        self._color = self.color_shell._color

    def printsh(self, color, text, end="\n"):
        """
        Method for not so common colors. But color should be a valid ANSI control sequence.
        """

        print(self._color(color, text), end=end)

    def danger(self, result, end="\n"):
        self.printsh(SHELL_COLOR_DANGER, result, end=end)

    def alert(self, result, end="\n"):
        self.printsh(SHELL_COLOR_ALERT, result, end=end)

    def warning(self, result, end="\n"):
        self.printsh(SHELL_COLOR_WARNING, result, end=end)

    def info(self, result, end="\n"):
        self.printsh(SHELL_COLOR_INFO, result, end=end)

    def success(self, result, end="\n"):
        self.printsh(SHELL_COLOR_SUCCESS, result, end=end)

    def lmn(self, result, end="\n"):
        self.printsh(SHELL_COLOR_LINUXMUSTER, result, end=end)


# Mostly copied from https://github.com/not-kennethreitz/blindspin
class Spinner(object):
    spinner_cycle = itertools.cycle(u'⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')

    def __init__(self, color=SHELL_COLOR_WARNING, progress=False):
        """
        A basic CLI spinner to animate a long process.

        :param color: A valid ANSI control sequence color for shell ouput, like  '\033[93m'.
        See defined colors in this module.
        :type color: basestring
        :param progress: If true, try to display one line per text to print (does not always work).
        If false, all lines are always replaced by the next line.
        :type progress: bool
        """


        self.color = color
        self.progress = progress
        self.stop_running = None
        self.spin_thread = None
        self.text = ""
        self.last_text = ""
        self.update = False

    def start(self):
        if sys.stdout.isatty():
            # Hide cursor
            print('\033[?25l', end="")

            self.stop_running = threading.Event()
            self.spin_thread = threading.Thread(target=self.init_spin)
            self.spin_thread.start()

    def stop(self):
        if self.spin_thread:
            # Restore cursor
            print('\033[?25h', end="")

            self.stop_running.set()
            self.spin_thread.join()

    def init_spin(self):
        last_time = time.time()
        next_val = next(self.spinner_cycle)
        while not self.stop_running.is_set():
            sys.stdout.flush()
            sys.stdout.write(f"  {self.color}{next_val}{SHELL_COLOR_ENDC}  {self.text}")
            if self.update and self.progress:
                sys.stdout.write('\n')
                self.update = False
            if time.time() - last_time > 0:
                last_time = time.time()
                next_val = next(self.spinner_cycle)

            sys.stdout.write('\r')

    def print(self, text):
        self.last_text = self.text
        self.text = text
        self.update = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        sys.stdout.write(f"  {SHELL_COLOR_SUCCESS}{u'✓'}{SHELL_COLOR_ENDC}  {self.last_text}")
        return False
