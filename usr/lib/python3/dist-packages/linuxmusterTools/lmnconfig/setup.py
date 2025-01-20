import os
import logging

from linuxmusterTools.lmnfile import LMNFile


logger = logging.getLogger(__name__)

class SetupConfig:

    def __init__(self, school='default-school'):
        # TODO: setup path for multischool ?
        setup_config_path = f'/var/lib/linuxmuster/setup.ini'

        if os.path.isfile(setup_config_path) and school == 'default-school':
            with LMNFile(setup_config_path, 'r') as config:
                self.config = config.read()
        else:
            logger.warning(f"No setup config found for the school {school}")
            self.config = {}
