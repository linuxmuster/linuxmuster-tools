import os
import re
import glob
from dataclasses import (dataclass)


FILENAME_REGEX = re.compile(r"(?P<type>[a-z]+)\-(?P<lang>[A-Z]+)\-(?P<count>\d+)\-template\.tex")
TEMPLATES_DIR = "/var/lib/lmntools/templates/"

@dataclass
class LatexTemplate():
    count: int
    filename: str
    lang: str
    type: str

    def __post_init__(self):
        self.count = int(self.count)

class LatexTemplates:

    def __init__(self):
        self.templates = {}
        self.load()

    def load(self):
        for path in glob.glob(f'{TEMPLATES_DIR}/*.tex'):
            filename = path.split('/')[-1]
            if data := re.match(FILENAME_REGEX, filename):
                self.templates[filename] = LatexTemplate(filename=filename, **data.groupdict())


