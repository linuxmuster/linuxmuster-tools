import os
import logging
from collections import OrderedDict
from configparser import ConfigParser
from pathlib import Path

from linuxmusterTools.lmnfile import LMNFile


logger = logging.getLogger(__name__)

SOPHOMORIX_INI_PATH = "/usr/share/sophomorix/devel/sophomorix.ini"

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
        self.path = SOPHOMORIX_INI_PATH
        self.data = ConfigParser(delimiters=("=",), dict_type=MultiOrderedDict, strict=False)
        self.data.read_string(self._read_expanded())
        self.sections = list(self.data.keys())

        self.dict = {}
        for section in self.sections:
            self.dict[section] = {}
            for key,value in self.data[section].items():
                self.dict[section][key] = self.sanitize(value)

        self.computerrole = [s.replace('computerrole.', '') for s in self.sections if s.startswith('computerrole')]

        # Whether a computer role gets a real machine account in the AD, as
        # opposed to a DNS node only. This is what decides if the NetBIOS
        # limits apply to the hostname of a device: an account name is a
        # sAMAccountName, capped at 15 characters plus the trailing '$'.
        # https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/naming-conventions-for-computer-domain-site-ou
        self.computer_account = {}
        for role in self.computerrole:
            value = self.dict[f'computerrole.{role}'].get('computer_account')
            if value is None:
                logger.warning(
                    f"computerrole.{role} has no COMPUTER_ACCOUNT in {self.path}, assuming FALSE"
                )
            self.computer_account[role] = str(value).strip().upper() == 'TRUE'

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

    def _read_expanded(self):
        """
        Read sophomorix.ini and expand its tabs.

        The file indents its keys with a tabulation in most sections and
        with eight spaces in others, sometimes within the same section.
        configparser reads a line indented deeper than the previous key as
        a continuation of its value, so a space indented key following a
        tab indented one is swallowed into the value above it: 53 keys of
        the shipped file are lost that way, the COMPUTER_ACCOUNT of all 15
        computer roles among them. Expanding tabs to eight columns puts
        both forms at the same level, and leaves genuine continuation
        lines - indented further than eight columns - untouched.

        :return: The content of the file, empty if it can not be read
        :rtype: str
        """


        try:
            return Path(self.path).read_text().expandtabs(8)
        except OSError as e:
            logger.warning(f"Could not read {self.path}: {e}")
            return ""

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
