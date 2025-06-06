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

schoolclass_students_groups_to_update = set()

for entry in entries:
    user = entry["user"]

    if entry["role"] == 'student':

        # If a student is added to the class 7a, then the group 7a-students must
        # be updated

        schoolclass_students_groups_to_update.add(entry["adminclass"])


for schoolclass in schoolclass_students_groups_to_update:
    lprint.info(f"Updating students group of schoolclass {schoolclass}")
    schoolclass_group = LMNSchoolclass(schoolclass)
    schoolclass_group.students_group.fill_members()
