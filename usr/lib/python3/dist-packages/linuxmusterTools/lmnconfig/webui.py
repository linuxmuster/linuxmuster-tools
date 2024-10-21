import os
import logging

from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.common import WEBUI_IMPORT


class CustomFieldsConfig:

    def __init__(self, school='default-school'):
        custom_config_path = f'/etc/linuxmuster/sophomorix/{school}/custom_fields.yml'

        if WEBUI_IMPORT:
            self.config = {}
            return
        elif os.path.isfile(custom_config_path):
            with LMNFile(custom_config_path, 'r') as config:
                self.config = config.read()
        else:
            logging.warning(f"No custom fields config found for the school {school}")
            self.config = {}

        for role in ['globaladministrators', 'schooladministrators', 'students', 'teachers']:
            tmp_role_config = {}

            for config_type in ['custom', 'customDisplay', 'customMulti', 'passwordTemplates', 'proxyAddresses']:
                tmp_role_config[config_type] = self.config.get(config_type, {}).get(role, {})

            setattr(self, role, tmp_role_config)
