import os
import logging

from linuxmusterTools.lmnfile import LMNFile


logger = logging.getLogger(__name__)

class SophomorixConfig:

    def __init__(self, school='default-school'):
        prefix = ""
        if school != 'default-school':
            prefix = f"{school}."
        sophomorix_config_path = f'/etc/linuxmuster/sophomorix/{school}/{prefix}school.conf'

        if os.path.isfile(sophomorix_config_path):
            with LMNFile(sophomorix_config_path, 'r') as config:
                self.config = config.read()
        else:
            logger.warning(f"No sophomorix config found for the school {school}")
            self.config = {}
