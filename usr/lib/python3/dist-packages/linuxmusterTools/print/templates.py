import os
import re
import glob
from dataclasses import (dataclass)


FILENAME_REGEX = re.compile(r"(?P<type>[a-z]+)\-(?P<lang>[A-Z]+)\-(?P<count>\d+)\-template\.tex")
TEMPLATES_DIR = "/var/lib/lmntools/templates/"

@dataclass
class LatexTemplate():
    count: str
    filename: str
    lang: str
    type: str

class LatexTemplates:

    def __init__(self):
        self.templates = {}
        self.load()

    def load(self):
        os.chdir(TEMPLATES_DIR)

        for filename in glob.glob('*.tex'):
            if data := re.match(FILENAME_REGEX, filename):
                self.templates[filename] = LatexTemplate(filename=filename, **data.groupdict())


