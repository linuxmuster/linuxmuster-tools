import itertools
import sys
import threading
import time

WARNING = '\033[93m'
SUCCESS = '\033[92m'
ALERT = '\033[38;5;208m'
DANGER = '\033[91m'
INFO = '\033[96m'
LINUXMUSTER = '\033[1m\033[38;5;214m'
ENDC = '\033[0m'
# For more definitions, see : https://misc.flogisoft.com/bash/tip_colors_and_formatting


class ColorShell:

    def danger(self, result, end="\n"):
        print(f'{DANGER}{result}{ENDC}', end=end)

    def alert(self, result, end="\n"):
        print(f'{ALERT}{result}{ENDC}', end=end)

    def warning(self, result, end="\n"):
        print(f'{WARNING}{result}{ENDC}', end=end)

    def info(self, result, end="\n"):
        print(f'{INFO}{result}{ENDC}', end=end)

    def success(self, result, end="\n"):
        print(f'{SUCCESS}{result}{ENDC}', end=end)

    def lmn(self, result, end="\n"):
        print(f'{LINUXMUSTER}{result}{ENDC}', end=end)

    def printsh(self, text, color, end="\n"):
        print(f'{color}{text}{ENDC}', end=end)

# Mostly copied from https://github.com/not-kennethreitz/blindspin
class Spinner(object):
    spinner_cycle = itertools.cycle(u'⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')

    def __init__(self, color=WARNING):
        self.color = color
        self.stop_running = None
        self.spin_thread = None
        self.text = ""
        self.last_text = ""

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
            sys.stdout.write(f"  {self.color}{next_val}{ENDC}  {self.text}")
            if time.time() - last_time > 0.001:
                last_time = time.time()
                next_val = next(self.spinner_cycle)
            sys.stdout.write('\r')

    def print(self, text):
        self.last_text = text
        self.text = text

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        sys.stdout.write(f"  {SUCCESS}{u'✓'}{ENDC}  {self.last_text}")
        return False