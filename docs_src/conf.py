#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import builtins
import subprocess
from datetime import datetime

import linuxmusterTools.ldapconnector
import sphinx_rtd_theme


# Fix gettext syntax
builtins._ = lambda x:x

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosummary',
    'autoapi.extension',
    'myst_parser',
]
autosummary_generate = True

autoapi_dirs = ['../usr/lib/python3/dist-packages/linuxmusterTools']
autoapi_type = "python"
autoapi_ignore = ["*/conf.py", "*/examples/*", "*/pytests/*", "*/install-scripts/*", "*/WIP/*"]
# Drop imported-members: the packages re-export their submodules (from .x
# import *), which otherwise documents every object twice (package index +
# module index) and floods the build with "duplicate description" warnings.
autoapi_options = ['members', 'undoc-members', 'show-inheritance', 'special-members']
# autoapi resolves imports statically and can't follow the cross-module
# constants pulled in via star-imports (LDAP_CONTEXT, SAMBA_* ...); the
# warnings are false positives.
suppress_warnings = ['autoapi.python_import_resolution',
                     # The module READMEs keep GitHub-relative links to each
                     # other (../<module>/README.md); they don't resolve as
                     # Sphinx cross-references but must stay valid on GitHub.
                     'myst.xref_missing']

# Turn ## headings of the included READMEs into anchor targets so their
# in-page [...](#section) links work.
myst_heading_anchors = 3

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = 'linuxmuster-tools7'
year = datetime.now().strftime('%Y')
copyright = f'Arnaud Kientz - {year}'
author = 'Arnaud Kientz'

def setup(app):
    app.add_css_file("theme_overrides.css")

version = subprocess.check_output('apt-cache policy linuxmuster-tools7 | grep Candidat', shell=True).decode().split(':')[1].strip()
release = version

language = 'en_GB'
exclude_patterns = []
pygments_style = 'sphinx'
todo_include_todos = False

html_theme = 'sphinx_rtd_theme'
html_logo = '_static/logo.png'
html_static_path = ['_static']
html_sidebars = {
    '**': [
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
    ]
}

htmlhelp_basename = 'linuxmuster-tools7doc'

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

latex_documents = [
    (master_doc, 'linuxmuster-tools7.tex', 'linuxmuster-tools7 Documentation',
     'Arnaud Kientz', 'manual'),
]

man_pages = [
    (master_doc, 'linuxmuster-tools7', 'linuxmuster-tools7 Documentation',
     [author], 1)
]


texinfo_documents = [
    (master_doc, 'linuxmuster-tools7', 'linuxmuster-tools7 Documentation',
     author, 'linuxmuster-tools7', 'One line description of project.',
     'Miscellaneous'),
]

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
