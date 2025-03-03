import os
import logging
from collections import OrderedDict
from configparser import ConfigParser

from linuxmusterTools.lmnfile import LMNFile


logger = logging.getLogger(__name__)

class SchoolConfig:

    def __init__(self, school='default-school'):
        prefix = ""
        if school != 'default-school':
            prefix = f"{school}."
        sophomorix_config_path = f'/etc/linuxmuster/sophomorix/{school}/{prefix}school.conf'

        if os.path.isfile(sophomorix_config_path):
            with LMNFile(sophomorix_config_path, 'r') as config:
                self.config = config.read()
        else:
            logger.warning(f"No sophomorix school config found for the school {school}")
            self.config = {}

class MultiOrderedDict(OrderedDict):

    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super().__setitem__(key, value)

class SophomorixIni:

    def __init__(self):
        self.path = "/usr/share/sophomorix/devel/sophomorix.ini"
        self.data = ConfigParser(delimiters=("=",), dict_type=MultiOrderedDict, strict=False)
        self.data.read(self.path)
        self.sections = list(self.data.keys())

        self.dict = {}
        for section in self.sections:
            self.dict[section] = {}
            for key,value in self.data[section].items():
                self.dict[section][key] = self.sanitize(value)

        self.computerrole = [s.replace('computerrole.', '') for s in self.sections if s.startswith('computerrole')]

        # TODO: should be loaded, not hardcoded
        self.clientrole = [
            'classroom-teachercomputer',
            'classroom-studentcomputer',
            'faculty-teachercomputer',
            'staffcomputer',
            'thinclient',
            'iponly',
        ]
        self.userrole = list(self.dict['ROLE_USER'].keys())

    @staticmethod
    def sanitize(value):
        if '\n' in value:
            result = value.split('\n')
            for idx,v in enumerate(result):
                result[idx] = v.split("#")[0].strip()
            return result
        else:
            return value.split("#")[0].strip()

    def get(self, section, key):
        if section not in self.sections:
            raise KeyError(f"Section {section} not found in sophomorix.ini.")

        section = self.data[section]

        if key not in section:
            raise KeyError(f"Key {key} not found in the section {section} of sophomorix.ini.")

        return self.sanitize(section[key])


class SophomorixConf:

    def __init__(self):
        self.path = f'/etc/linuxmuster/sophomorix/sophomorix.conf'

        if os.path.isfile(self.path):
            with LMNFile(self.path, 'r') as config:
                self.data = config.data
        else:
            logger.warning(f"No sophomorix.conf found on the server.")
            self.data = {}
