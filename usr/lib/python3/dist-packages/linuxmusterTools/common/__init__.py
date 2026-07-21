from .convert import *
from .checks import *
from .parsers import *
from .color_shell import *
from .exceptions import *

Validator = NameChecker()
lprint = PrintShell()
lcolor = ColorShell()
spinner = Spinner()

try:
    from aj.plugins.lmn_common.api import ldap_config as params
    WEBUI_IMPORT = True
except ImportError as e:
    WEBUI_IMPORT = False