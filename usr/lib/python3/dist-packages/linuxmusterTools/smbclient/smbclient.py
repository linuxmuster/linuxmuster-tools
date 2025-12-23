"""
A smbclient utility to perform some basic operations on the fileserver.
"""


# Actually still in experimental mode
from ..ldapconnector import LMNLdapReader as lr
from ..lmnconfig import SAMBA_DOMAIN
import subprocess

class LMNSMBClient:
    def __init__(self, school='default-school'):
        self.switch(school)

    def switch(self, school):
        schools = lr.getval('/schools', 'ou')
        if school in schools:
            self.school = school
        else:
            raise Exception(f"School {school} not found.")

    def _execute(self, subcmd):
        with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
            passwd = admpwd.readline().strip()

        cmd = [
            "/bin/smbclient",
            f"-U administrator%{passwd}",
            f"//{SAMBA_DOMAIN}/{self.school}",
            "-c",
            subcmd,
        ]

        result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        out, err = result.communicate()

        # Clean up memory
        passwd = ''
        cmd = []
        result = ''

        return out

    def list(self, path):
        """
        Return a list of files and directories in path, if existing.

        :param path: Samba path like students/10a/myuser/transfer
        :return: list
        """


        cmd = f"dir \"{path}/*\";"
        lines = self._execute(cmd).decode().split('\n')

        filelist = []
        for idx, line in enumerate(lines):
            details = line.split()
            # [filename/dirname, type, size, split date...]
            try:
                name = details[0]

                # Unfortunately smbclient doesn't always throw an error, and the return code may be 0
                # even if there was a problem. So it's necessary to check manually if the first result is '.'
                # If not, the first line is mostly the error.

                if idx == 0 and name != '.':
                    raise Exception(f'There was a problem with the list command: {line}')

                objtype = 'file' if details[1] != 'D' else 'directory' # Should be 'N' for files
                filelist.append({'name': name, 'type': objtype, 'size': details[2]})
            except IndexError:
                # Should be the end of list
                break

        return filelist

    def deltree(self, path):
        """
        Delete recursively the content of a directory.

        :param path: Samba path like students/attic/myuser
        :return: list
        """


        cmd = f"deltree \"{path}\";"
        self._execute(cmd)


