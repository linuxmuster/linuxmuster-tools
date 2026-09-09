#! /usr/bin/env python3

# This script is part of the sophomorix project and intended to add
# CN group of parents for new students
# DO NOT EDIT OR REMOVE IT !

import sys
from linuxmusterTools.common import parse_add_log, lprint
from linuxmusterTools.ldapconnector import LMNUser, LMNSchoolclass


epoch = sys.argv[1]
school = sys.argv[2]

if epoch is None:
    updates = parse_add_log(today=True)
    timestamps = list(updates.keys())
    timestamps.sort()
    epoch = timestamps[-1]
    entries = updates[epoch]
else:
    entries = parse_add_log(epoch=epoch)

schoolclass_groups_to_update = {
    'default-school': {
        'students': set(),
        'teachers': set(),
        'parents': set()
    }
}

for entry in entries:
    user = entry["user"]
    school = entry["school"]

    if school not in schoolclass_groups_to_update:
        schoolclass_groups_to_update[school] = {
            'students': set(),
            'teachers': set(),
            'parents': set()
        }

    if entry["role"] == 'student':

        # If a student is added to the class 7a, then the group 7a-students must
        # be updated

        schoolclass_groups_to_update[school]['students'].add(entry["adminclass"])

for school, groups in schoolclass_groups_to_update.items():
    for schoolclass in groups['students']:
        lprint.lmn(f"Updating students group of schoolclass {schoolclass} in {school}")
        try:
            schoolclass_group = LMNSchoolclass(schoolclass, school=school)
            schoolclass_group.students_group.fill_members()
        except Exception as e:
            # A single failing schoolclass must not abort the whole hook: the
            # users have already been added by sophomorix at this point.
            lprint.danger(f"Could not update the students group of {schoolclass} in {school}: {str(e)}")
