#! /usr/bin/env python3

"""
Script to reset internet (set on) for all students.
This script can be used as cronjob each night to fix the forgotten
permissions set in sessions of teachers.
"""

from linuxmusterTools.common import lprint
from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from linuxmusterTools.samba_util import GroupManager


# Get a "raw" list of all students ("raw" means without parents attributes, to speed up the process).

students = lr.get('/rawroles/student')
to_fix = [student['cn'] for student in students if not student['internet']]

if to_fix:
    for cn in to_fix:
        lprint.success(f"Fixing internet for student {cn}")
    GroupManager().add_members('internet', to_fix)