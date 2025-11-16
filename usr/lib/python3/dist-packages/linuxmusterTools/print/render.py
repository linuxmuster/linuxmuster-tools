import os
import subprocess
from jinja2 import Environment, FileSystemLoader


OUTPUT_DIR = "/var/lib/lmntools/print/"
TEMPLATES_DIR = "/var/lib/lmntools/templates/"


class LatexRenderer:

    def __init__(self, template_obj, data, caller="", vars={}):
        # Option 1 per page ? only for PW
        self.data = data
        self.caller = caller
        self.template_obj = template_obj

        self.vars = vars
        self._sanitize()

    def _sanitize(self):
        """
        Filter some common problems for LaTeX compilation, like _ => \\_
        """


        tmp_vars = {}
        for key, value in self.vars.items():
            tmp_vars[key] = value.replace("_", "\\_")
        self.vars = tmp_vars

    def _clean(self):
        for ext in [".log", ".aux", ".toc", ".dvi", ".ps", ".pre", ".thm", ".pyg"]:
            tmp_file = self.destination_file.replace(".tex", ext)
            if os.path.isfile(tmp_file):
                os.unlink(tmp_file)

    def render(self):
        """
        Render the vars in the jinja template
        """


        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

        try:
            # Check number of entries and number of pages

            self.template = self.env.get_template(self.template_obj.filename)

            # Split into multiples pages if too much data
            count = self.template_obj.count
            datablocks = [
                self.data[count*i:count*i+count]
                for i in range(len(self.data)//count+1)
                if count*i != len(self.data)
            ]

            self.out = self.template.render(datablocks=datablocks, **self.vars)
        except Exception as e:
            raise

    def compile(self):
        """
        Prepare the tex file and compile, while trying to catch the compilations errors.

        :return: PDF path as string
        """


        self.render()

        if self.template_obj.type == "schoolclass":
            output_file = f"{self.caller}-schoolclass-{self.vars['schoolclass']}.tex"

        self.destination_file = os.path.join(OUTPUT_DIR, output_file)

        with open(self.destination_file, 'w') as f:
            f.write(self.out)

        p = subprocess.Popen(
            [
                '/bin/pdflatex',
                '-halt-on-error',
                '-interaction=nonstopmode',
                self.destination_file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=OUTPUT_DIR
        )

        stdout, stderr = p.communicate()

        self._clean()

        if p.returncode > 0:
            # Isolate error for shell in red --> not pretty readable for JSON response in API
            # log = stdout.decode().split("\n")
            # for idx,line in enumerate(log):
            #     if line.startswith("!"):
            #         log[idx] = f"\033[91m{line}\033[0m"

            raise Exception(f"Compilation failed: \n{stdout.decode()}")

        return self.destination_file.replace(".tex", ".pdf")

