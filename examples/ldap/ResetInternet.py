#! /usr/bin/env python3

"""
Script to reset internet (set on) for all students.
This script can be used as cronjob each night to fix the forgotten
permissions set in sessions of teachers.
"""

from linuxmusterTools.common import lprint
from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNMgmtGroup


# Get a "raw" list of all students ("raw" means without parents attributes, to speed up the process).

students = lr.get('/rawroles/student')
total = len(students)
internet_group = LMNMgmtGroup('internet')

for idx, student in enumerate(students):
    if not student['internet']:
        lprint.success(f"Fixing internet for student {student['cn']}")
        internet_group.add_member(student['cn'])