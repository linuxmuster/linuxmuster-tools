import logging
from pathlib import Path

from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.common import WEBUI_IMPORT
from linuxmusterTools.common.timestamps import get_utc_mtime


logger = logging.getLogger(__name__)

_CACHE = {}

class CustomFieldsConfig:

    def __init__(self, school='default-school'):
        if WEBUI_IMPORT:
            self.config = {}
            return

        self.config = self._load(school)

        for role in ['globaladministrators', 'schooladministrators', 'students', 'teachers']:
            tmp_role_config = {}

            for config_type in ['custom', 'customDisplay', 'customMulti', 'passwordTemplates', 'proxyAddresses']:
                tmp_role_config[config_type] = self.config.get(config_type, {}).get(role, {})

            setattr(self, role, tmp_role_config)

    @staticmethod
    def _load(school):
        """
        Return the parsed custom fields config of a school, reading the file
        again only if it changed since the last read. Every ldap request of
        the ldapconnector instantiates this class, so parsing the yaml file
        each time cost 12-19 ms per request.

        The returned dict is shared between callers and must not be modified.

        :param school: school name
        :type school: basestring
        :return: parsed custom_fields.yml, empty dict if the file doesn't exist
        :rtype: dict
        """

        path = Path(f'/etc/linuxmuster/sophomorix/{school}/custom_fields.yml')
        mtime = get_utc_mtime(path)

        if mtime is None:
            #logger.warning(f"No custom fields config found for the school {school}")
            return {}

        cached = _CACHE.get(school)

        # Check for changes since the last request.
        if cached and cached[0] == mtime:
            return cached[1]

        with LMNFile(path, 'r') as config:
            data = config.read()

        _CACHE[school] = (mtime, data)
        return data
