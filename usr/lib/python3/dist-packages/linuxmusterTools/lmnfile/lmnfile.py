"""
Classes definitions to read, parse and save config files.
"""

import os
import os.path
import logging
import abc
import csv
import re
import magic
import filecmp
import stat
import tempfile
import time
import yaml
from configobj import ConfigObj

from .fieldnames import csv_fieldnames


logger = logging.getLogger(__name__)

# Allow 1 MiB for csv
csv.field_size_limit(2**20)

ALLOWED_PATHS = [
    '/etc/linuxmuster/api/config.yml',                  # Api settings
    '/etc/linuxmuster/webui/config.yml',                # Webui settings
    '/etc/linuxmuster/tools/password_constraints.yml',  # LMNTools password constraints settings
    '/etc/linuxmuster/sophomorix/',                     # school.conf or *.csv in lmn_settings, lmn_devices and lmn_users
    '/srv/linbo',                                       # lmn_linbo for start.conf
    '/etc/linuxmuster/subnets.csv',                     # lmn_settings subnets configuration
    '/etc/linuxmuster/holidays.yml',                    # lmn_settings holidays configuration
    '/var/lib/linuxmuster/setup.ini',                   # lmn_settings
    '/tmp/setup.ini',                                   # setup wizard during install
    '/usr/lib/linuxmuster-webui/plugins',               # lmn_permissions
]

EMPTY_LINE_MARKER = '###EMPTY#LINE'
HEADER_MARKER = '#HEADERS#'
BOM_MARKER = b'\xef\xbb\xbf'


def convertBool(boolean):
    if type(boolean) is bool:
        return 'yes' if boolean else 'no'
    return boolean


class LMNFile(metaclass=abc.ABCMeta):
    """
    Meta class to handle all type of config file used in linuxmuster's project,
    e.g. ini, csv, linbo config files.
    """

    def __new__(
        cls, file, mode, delimiter=';', fieldnames=None, convert_values=True
    ):
        """
        Parse the extension of the file and choose the right subclass to handle
        the file.

        :param file: File to open
        :type file: string
        :param mode: Read, write, e.g. 'r' or 'wb'
        :type mode: string
        :param delimiter: Useful for CSV files
        :type delimiter: string
        :param fieldnames: Useful for CSV files
        :type fieldnames: list of strings
        :param convert_values: Convert ConfigLoader values to Python types
        :type convert_values: bool
        """

        # Cannot filter start.conf with extension
        if file.split('/')[-1].startswith('start.conf') and os.path.splitext(file)[-1] != '.vdi':
            obj = object.__new__(StartConfLoader)
            obj.__init__(
                file, mode, delimiter=delimiter, fieldnames=fieldnames,
                convert_values=convert_values
            )
            return obj

        ext = os.path.splitext(file)[-1]
        for child in cls.__subclasses__():
            if child.hasExtension(ext):
                obj = object.__new__(child)
                obj.__init__(
                    file, mode, delimiter=delimiter, fieldnames=fieldnames,
                    convert_values=convert_values
                )
                return obj

    def __init__(
        self, file, mode, delimiter=';', fieldnames=None, convert_values=True
    ):
        self.file = file
        self.opened = ''
        self.data = ''
        self.mode  = mode
        self.encoding = self.detect_encoding()
        self.comments = []
        self.check_allowed_path()
        self.delimiter = delimiter
        self.convert_values = convert_values
        self.has_BOM = False

        if self.file.endswith('.csv'):
            # Fieldnames aliases for some common CSV files
            for model in sorted(csv_fieldnames):
                # dict must be sorted, because students is a prefix of extrastudents
                if self.file.startswith('/etc/linuxmuster/') \
                    and self.file.endswith(f'{model}.csv'):
                    self.fieldnames = csv_fieldnames[model]
                    break
            else:
                self.fieldnames = fieldnames

            # Check BOM for sophomorix-check
            if os.path.isfile(self.file):
                with open(self.file, 'rb') as f:
                    if f.read(3).startswith(BOM_MARKER):
                        self.has_BOM = True

    @classmethod
    def hasExtension(cls, ext):
        """
        Determine if file should be handled here.

        :param ext: Extension of a file, e.g. ini
        :type ext: string
        :return: File handled or not
        :rtype: bool
        """

        if ext in cls.extensions:
            return True
        return False

    @abc.abstractmethod
    def __enter__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError

    def read(self):
        return self.data

    def backup(self):
        """
        Create a backup of a file if in allowed paths, but on ly keeps 10 backups.
        Backup files names scheme is `.<name>.bak.<timestamp>`
        """

        if not os.path.exists(self.file):
            return

        folder, name = os.path.split(self.file)
        backups = sorted([x for x in os.listdir(folder) if x.startswith(f'.{name}.bak.')])
        while len(backups) > 10:
            os.unlink(os.path.join(folder, backups[0]))
            backups.pop(0)

        backup_path = folder + '/.' + name + '.bak.' + str(int(time.time()))
        with open(backup_path, 'w', encoding=self.encoding) as backup, open(self.file, 'r', encoding=self.encoding) as f:
            f.seek(0)
            backup.write(f.read())

        # Set same permissions as original file
        perms = os.stat(self.file).st_mode
        os.chmod(backup_path, perms)

    # @abc.abstractmethod
    # def __iter__(self):
    #     raise NotImplementedError
    #
    # @abc.abstractmethod
    # def __next__(self):
    #     raise NotImplementedError

    def check_allowed_path(self):
        """
        Check path before modifying files for security reasons.

        :return: File path in allowed paths.
        :rtype: bool
        """


        allowed_path = False
        for rootpath in ALLOWED_PATHS:
            if rootpath in self.file:
                allowed_path = True
                break

        if allowed_path and '..' not in self.file:
            return True
        raise IOError("Access refused.")  # skipcq: PYL-E0602

    def detect_encoding(self):
        """
        Try to detect encoding of the file through magic numbers.

        :return: Detected encoding
        :rtype: string
        """


        if not os.path.isfile(self.file):
            logger.debug(f'Detected encoding for {self.file} : no file, using utf-8')
            return 'utf-8'
        loader = magic.Magic(mime_encoding=True)
        encoding = loader.from_file(self.file)
        if 'ascii' in encoding or encoding == "binary":
            logger.debug(f'Detected encoding for {self.file} : ascii, but using utf-8')
            return 'utf-8'
        logger.debug(f'Detected encoding for {self.file} : {encoding}')
        return encoding


class LinboLoader(LMNFile):
    """
    Handler for linbo's cloop informations files.
    """

    extensions = ['.desc', '.reg', '.postsync', '.info', '.macct', '.prestart']

    def __enter__(self):
        self.opened = open(self.file, self.mode, encoding=self.encoding)
        return self.opened

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.opened.close()


class YAMLLoader(LMNFile):
    """
    Handler for yaml files.
    """

    extensions = ['.yml', '.vdi']

    def __enter__(self):
        if os.geteuid() == 0:
            # Creating empty file if it does not exist
            if not os.path.exists(self.file):
                open(self.file, 'w').close()
            os.chmod(self.file, 384)  # 0o600
        self.opened = open(self.file, 'r')
        if 'r' in self.mode or '+' in self.mode:
            self.data = yaml.load(self.opened, Loader=yaml.SafeLoader)
        return self

    def write(self, data):
        tmp = self.file + '_tmp'
        with open(tmp, 'w', encoding=self.encoding) as f:
            f.write(
                yaml.safe_dump(
                    data,
                    default_flow_style=False,
                    encoding='utf-8',
                    allow_unicode=True
                ).decode('utf-8')
            )
        if not filecmp.cmp(tmp, self.file):
            self.backup()
            os.rename(tmp, self.file)
        else:
            os.unlink(tmp)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.opened.close()

class CSVLoader(LMNFile):
    """
    Handler for csv files.
    """

    extensions = ['.csv']

    def __enter__(self):
        self.fix_bom()
        self.opened = open(self.file, 'r', encoding=self.encoding)
        if 'r' in self.mode or '+' in self.mode:
            # Removing leading and trailing spaces for all fields
            trim = []
            headers_found = False
            for line in self.opened:

                if not headers_found and HEADER_MARKER in line:
                    # Only the first HEADERS marker will be used
                    self.fieldnames = [
                        field.strip()
                        for field in line.replace(HEADER_MARKER, "").split(self.delimiter)
                    ]
                    headers_found = True
                    continue

                trim.append(self.delimiter.join(
                    [field.strip() for field in line.split(self.delimiter)]
                ))
            self.data = csv.DictReader(
                (line if len(line) > 3 else EMPTY_LINE_MARKER for line in trim),
                delimiter = self.delimiter,
                fieldnames = self.fieldnames
            )
        return self

    def read(self):
        return list(self.data)

    def fix_bom(self):
        if self.has_BOM:
            if self.encoding == 'utf-8':
                with open(self.file, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                with open(self.file, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                logger.info(f"Can not fix BOM with encoding: {self.encoding}")

    def write(self, data):
        tmp = self.file + '_tmp'
        with open(tmp, 'w', encoding=self.encoding) as f:
            writer = csv.DictWriter(
                f,
                delimiter = self.delimiter,
                fieldnames = self.fieldnames,
                lineterminator = '\n'
            )
            for elt in data:
                first_field = elt[self.fieldnames[0]]
                if first_field in ['', EMPTY_LINE_MARKER]:
                    f.write(first_field.replace(EMPTY_LINE_MARKER, '') + '\n')
                elif first_field.startswith('#'):
                    f.write(first_field + '\n')
                else:
                    writer.writerow(elt)
        if not filecmp.cmp(tmp, self.file):
            self.backup()
            os.rename(tmp, self.file)
        else:
            os.unlink(tmp)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.opened:
            self.opened.close()


class ConfigLoader(LMNFile):
    extensions = ['.ini', '.conf']

    def __enter__(self):
        if os.path.isfile(self.file):
            self.opened = open(self.file, 'r', encoding=self.encoding)
            source = self.file
        elif 'w' in self.mode:
            source = None
        else:
            raise FileNotFoundError(f'File {self.file} not found.')

        self.data = ConfigObj(
            source, encoding='utf-8',
            write_empty_values=True,
            stringify=True,
            list_values=False
        )
        self.data.filename = self.file
        if self.convert_values:
            for section, options in self.data.items():
                for key, value in options.items():
                    # isdigit() is False for a sign, and -1 is a valid value in
                    # school.conf (unlimited quota): it has to be converted too.
                    value = int(value) if re.fullmatch(r'[+-]?\d+', value) else value
                    value = True if value == 'yes' else value
                    value = False if value == 'no' else value
                    self.data[section][key] = value
        return self

    def __exit__(self, *args):
        if self.opened:
            self.opened.close()

    def write(self, data):
        for section, options in data.items():
            if section not in self.data:
                self.data[section] = {}
            for key, value in options.items():
                if self.convert_values:
                    value = 'yes' if value is True else value
                    value = 'no' if value is False else value
                self.data[section][key] = value

        # Replace the resolved target so an allowed configuration symlink keeps
        # pointing to the same file instead of being replaced by a regular file.
        target = os.path.realpath(self.file)
        folder, name = os.path.split(target)
        metadata = os.stat(target) if os.path.isfile(target) else None
        fd, tmp = tempfile.mkstemp(prefix=f'.{name}.', suffix='.tmp', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as f:
                self.data.write(f)
                f.flush()
                os.fsync(f.fileno())

            if metadata is not None:
                # chown may clear setuid/setgid bits, so restore the complete
                # permission mode afterwards.
                os.chown(tmp, metadata.st_uid, metadata.st_gid)
                os.chmod(tmp, stat.S_IMODE(metadata.st_mode))
                self.backup()

            os.replace(tmp, target)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

class StartConfLoader(LMNFile):

    extensions = []  # handled by filename check in __new__, not by extension

    def __enter__(self):
        self.data = {
            'config': {},
            'partitions': [],
            'os': [],
        }

        if os.path.isfile(self.file):
            self.opened = open(self.file, 'r', encoding=self.encoding)
        elif 'w' in self.mode:
            self.opened = None
        else:
            raise FileNotFoundError(f'File {self.file} not found.')

        # TODO: use new parser in linbo module
        if self.opened and ('r' in self.mode or '+' in self.mode):
            for line in self.opened:
                line = line.split('#')[0].strip()

                if line.startswith('['):
                    section = {}
                    section_name = line.strip('[]')
                    if section_name == 'Partition':
                        self.data['partitions'].append(section)
                    elif section_name == 'OS':
                        self.data['os'].append(section)
                    else:
                        self.data['config'][section_name] = section
                elif '=' in line:
                    k, v = line.split('=', 1)
                    v = v.strip()
                    if v in ['yes', 'no']:
                        v = v == 'yes'
                    section[k.strip()] = v
        return self

    def __exit__(self, *args):
        if self.opened:
            self.opened.close()

    def write(self, data):
        content = ''

        for section_name, section in data['config'].items():
            content += f'[{section_name}]\n'
            for k, v in section.items():
                content += f'{k} = {convertBool(v)}\n'
            content += '\n'

        for partition in data['partitions']:
            content += '[Partition]\n'
            for k, v in partition.items():
                if k[0] == '_':
                    continue
                content += f'{k} = {convertBool(v)}\n'
            content += '\n'

        for partition in data['os']:
            content += '[OS]\n'
            for k, v in partition.items():
                if k[0] == '_':
                    continue
                content += f'{k} = {convertBool(v)}\n'
            content += '\n'

        tmp = self.file + '_tmp'
        with open(tmp, 'w') as f:
            f.write(content)

        if os.path.isfile(self.file):
            if not filecmp.cmp(tmp, self.file):
                self.backup()
                os.rename(tmp, self.file)
            else:
                os.unlink(tmp)
        else:
            os.rename(tmp, self.file)

        os.chmod(self.file, 0o755)
