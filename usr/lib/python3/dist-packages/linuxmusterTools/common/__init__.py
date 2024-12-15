from .convert import *
from .checks import *


Validator = NameChecker()

try:
    from aj.plugins.lmn_common.api import ldap_config as params
    WEBUI_IMPORT = True
except ImportError as e:
    WEBUI_IMPORT = False