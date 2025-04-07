WARNING = '\033[93m'
SUCCESS = '\033[92m'
ALERT = '\033[38;5;208m'
DANGER = '\033[91m'
INFO = '\033[96m'
LINUXMUSTER = '\033[1m\033[38;5;214m'
ENDC = '\033[0m'
# For more definitions, see : https://misc.flogisoft.com/bash/tip_colors_and_formatting


class PrintShell:

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
