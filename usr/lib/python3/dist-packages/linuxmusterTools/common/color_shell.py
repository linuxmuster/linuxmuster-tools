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

    def danger(self, result):
        print(f'{DANGER}{result}{ENDC}')

    def alert(self, result):
        print(f'{ALERT}{result}{ENDC}')

    def warning(self, result):
        print(f'{WARNING}{result}{ENDC}')

    def info(self, result):
        print(f'{INFO}{result}{ENDC}')

    def success(self, result):
        print(f'{SUCCESS}{result}{ENDC}')

    def lmn(self, result):
        print(f'{LINUXMUSTER}{result}{ENDC}')

    def printsh(self, text, color):
        print(f'{color}{text}{ENDC}')

# Mostly copied from https://github.com/not-kennethreitz/blindspin
class Spinner(object):
    spinner_cycle = itertools.cycle(u'⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')

    def __init__(self, color=WARNING):
        self.color = color
        self.stop_running = None
        self.spin_thread = None

    def start(self):
        if sys.stdout.isatty():
            self.stop_running = threading.Event()
            self.spin_thread = threading.Thread(target=self.init_spin)
            self.spin_thread.start()

    def stop(self):
        if self.spin_thread:
            self.stop_running.set()
            self.spin_thread.join()

    def init_spin(self):
        while not self.stop_running.is_set():
            next_val = next(self.spinner_cycle)
            sys.stdout.write(f"  {self.color}{next_val}{ENDC}  ")
            sys.stdout.flush()
            time.sleep(0.07)
            sys.stdout.write('\r')

    def print(self, text):
        self.last_text = text
        print(text, end="\r")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        sys.stdout.write(f"  {SUCCESS}{u'✓'}{ENDC}  {self.last_text}")
        return False