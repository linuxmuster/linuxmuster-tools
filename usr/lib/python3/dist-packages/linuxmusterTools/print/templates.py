import os
import re
import glob
from dataclasses import dataclass
from ..ldapconnector import LMNLdapReader as lr


GLOBAL_FILENAME_REGEX = re.compile(r"(?P<type>[a-z]+)\-(?P<lang>[A-Z]+)\-(?P<count>\d+)\-template\.tex")

LMNTOOLS_TEMPLATES_DIR = "/var/lib/lmntools/templates/"
SOPHOMORIX_TEMPLATES_DIR = "/usr/share/sophomorix/lang/latex/templates/"
SOPHOMORIX_CONFIG_DIR = "/etc/linuxmuster/sophomorix"

@dataclass
class LatexTemplate():
    count: int
    filename: str
    lang: str
    package: str
    school: str
    type: str

    def __post_init__(self):
        self.count = int(self.count)

class LatexTemplates:
    """
    Class to handle all LaTeX templates.
    There's currently three sources of templates to print users lists (passwords, schoolclasses, etc ...):
    - Sophomorix's package directory: /usr/share/sophomorix/lang/latex/templates/
    - Sophomorix per school user's defined directory: /etc/linuxmuster/sophomorix/{school}/latex-templates/
    - LMNTools' package directory: /var/lib/lmntools/templates/

    In both package's directory the filenames should be like (<type>-<lang>-<count>-template.tex):
     - passwords-DE-1-template.tex
     - passwords-EN-36-template.tex
     - schoolclass-DE-32-template.tex
     - schoolclass-FR-32-template.tex
     - datalist-DE-1-template.tex
     - datalist-EN-36-template.tex

     In /etc/linuxmuster/sophomorix/{school}/latex-templates/, each filename should have the schoolname as prefix, i.e.
     something like: <schoolname>.<type>-<lang>-<count>-template.tex

    See https://github.com/linuxmuster/sophomorix4/blob/bionic/sophomorix-samba/lang/latex/README.latextemplates.
    """


    def __init__(self):
        self.templates = {}
        self.load()

    def load(self):

        # Load packages templates
        for path in glob.glob(f'{LMNTOOLS_TEMPLATES_DIR}/*.tex'):
            filename = path.split('/')[-1]
            if data := re.match(GLOBAL_FILENAME_REGEX, filename):
                self.templates[filename] = LatexTemplate(
                    filename=filename,
                    package="lmntools",
                    school="global",
                    **data.groupdict()
                )

        for path in glob.glob(f'{SOPHOMORIX_TEMPLATES_DIR}/*.tex'):
            filename = path.split('/')[-1]
            if data := re.match(GLOBAL_FILENAME_REGEX, filename):
                self.templates[filename] = LatexTemplate(
                    filename=filename,
                    package="sophomorix",
                    school="global",
                    **data.groupdict()
                )

        # School's and user's specific templates
        schools = lr.getval('/schools', "ou")
        for school in schools:
            school_filename_regex = re.compile(school + r'\.?(?P<type>[^-]*)-(?P<lang>[A-Z]+)-(?P<count>\d+)-template\.tex')
            for path in glob.glob(f'{SOPHOMORIX_CONFIG_DIR}/{school}/latex-templates/*.tex'):
                filename = path.split('/')[-1]
                if data := re.match(school_filename_regex, filename):
                    self.templates[filename] = LatexTemplate(
                        filename=filename,
                        package="school defined",
                        school=school,
                        **data.groupdict()
                    )

    def __str__(self):
        result = f"{'Filename':45} | {'Count':5} | {'Lang':4} | {'Type':15} | {'School':15} | Package\n"
        result += "-"*105 + "\n"
        for filename, t in self.templates.items():
            result += f"{filename:45} | {t.count:5} | {t.lang:4} | {t.type:15} | {t.school:15} | {t.package}\n"

        return result




