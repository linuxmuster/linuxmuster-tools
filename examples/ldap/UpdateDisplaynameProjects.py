#! /usr/bin/env python3

"""
Script to update all project's displayname attribute with a given template.
Use a fancy spinner to give some animation to the process.
"""

from linuxmusterTools.ldapconnector import LMNProjects
from linuxmusterTools.common import Spinner, SHELL_COLOR_INFO


# Get a list of all projects, but with write permissions in Ldap!
# Be careful to not change attributes if you not know what you are doing.

projects = LMNProjects()

# The color parameter sets the color of the spinner.
# It's possible to use the parameter progress too, to display all lines of the process.
with Spinner(color=SHELL_COLOR_INFO) as s:
    total = len(projects)
    for idx, (cn, project) in enumerate(projects.items()):
        s.print(f"[{idx+1}/{total}] Updating display name of project {cn}")

        # Save in LDAP
        project.setattr(data={'displayName': f"This is a great project {cn[2:].capitalize()}"})


    s.print(f"[{idx+1}/{total}] Update finished!")
