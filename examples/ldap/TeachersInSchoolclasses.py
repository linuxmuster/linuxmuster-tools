#! /usr/bin/env python3

"""
Script to get a list of all teacher's memberships in schoolclasses.
"""

from linuxmusterTools.common import lcolor
from linuxmusterTools.ldapconnector import LMNLdapReader as lr


teacher_cache = {}

# Get all schoolclasses, sorted by name
for schoolclass in lr.get('/schoolclasses', sortkey='cn'):

    # Teachers are stored in the attribute sophomorixAdmins
    teachers_cn = schoolclass['sophomorixAdmins']
    teachers = []

    for cn in teachers_cn:
        # Avoid requesting the same teachers more than once
        if cn not in teacher_cache:
            teacher = lr.get(f'/users/{cn}')
            teacher_name = f"{teacher['sn']} {teacher['givenName']}"
            teacher_cache[cn] = teacher_name

        teachers.append(teacher_cache[cn])

    # Some fancy colors
    print(f"{lcolor.green(schoolclass['cn']):<30} --> {lcolor.lmn(','.join(teachers))}")
    print("-"*80)

