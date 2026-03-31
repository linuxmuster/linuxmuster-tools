"""LINBO modules provided by this overlay package."""

from importlib import import_module
from pkgutil import extend_path
import subprocess

__path__ = extend_path(__path__, __name__)

from .wol import *
from .host_status import *
from .boot_logs import *
from .hooks import *
from .multicast import *
from .torrent import *
from .ssh import *
from .terminal import *
from .firmware import *
from .drivers import *
from .kernel import *
from .linbofs import *
from .wlan import *
from .image_sync import *
from .linbo_update import *
from .grub_generator import *
from .dhcp import *

# NOTE: hosts, config, grub, images, changes are provided by
# upstream linuxmuster-tools — do NOT re-export here

_LEGACY_MODULES = ("config", "images", "command", "changes", "hosts", "grub")


def __getattr__(name: str):
    """Resolve legacy upstream exports lazily.

    This keeps package import lightweight while still allowing callers to
    access upstream objects such as LinboConfigManager when available.
    """
    if name in _LEGACY_MODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module

    for module_name in _LEGACY_MODULES:
        try:
            module = import_module(f"{__name__}.{module_name}")
        except (ImportError, OSError, subprocess.SubprocessError):
            continue
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
