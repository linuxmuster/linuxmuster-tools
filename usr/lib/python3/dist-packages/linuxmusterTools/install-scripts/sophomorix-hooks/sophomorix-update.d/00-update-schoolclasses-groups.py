#! /usr/bin/env python3

# This script is part of the sophomorix project and intended to update
# CN of parents groups in students OU for students which attributes changed.
# DO NOT EDIT OR REMOVE IT !


import sys
from linuxmusterTools.common import *
from linuxmusterTools.ldapconnector import LMNUser, LMNSchoolclass, LMNStudent


epoch = sys.argv[1]
school = sys.argv[2]

if epoch is None:
    updates = parse_update_log(today=True)
    timestamps = list(updates.keys())
    timestamps.sort()
    epoch = timestamps[-1]
    entries = updates[epoch]
else:
    entries = parse_update_log(epoch=epoch)

schoolclass_students_groups_to_update = set()
schoolclass_parents_groups_to_update = set()
schoolclass_teachers_groups_to_update = set()

for entry in entries:
    user = entry["user"]
    changes = entry["changes"]

    if 'group' in changes:
        old_group, new_group = changes['group'].split('->')
        old_role, new_role = changes['role'].split('->')

        if old_role == new_role == 'student':

            # Student moving from a schoolclass to another, eventually attic

            if old_group != 'attic':
                # Removing student / student's parents from old students / parents group
                schoolclass_students_groups_to_update.add(old_group)
                schoolclass_parents_groups_to_update.add(old_group)

            if new_group == 'attic':
                # Delete CN in Student-Parents
                student = LMNStudent(user)
                student.parents_group.delete()

            else:
                # Adding student / student's parents to new students / parents group
                schoolclass_students_groups_to_update.add(new_group)
                schoolclass_parents_groups_to_update.add(new_group)

        elif old_group == 'teachers' and new_group == 'attic':

            # Teacher moves to attic to be deleted. It's necessary to remove this
            # teacher from all teachers groups

            teacher = LMNUser(user)
            for c in teacher.data['schoolclasses']:
                schoolclass_teachers_groups_to_update.add(c)

        elif old_group == 'parents' and new_group == 'attic':

            # Parent moves to attic to be deleted.

            parent = LMNUser(user)
            parent.get_children()

            # Remove parent from all parents groups in students
            for schoolclass in parent.children_schoolclasses:
                schoolclass_parents_groups_to_update.add(schoolclass)

            # Remove parent from Student-Parents' entries
            for student_cn in parent.children_cn:
                student = LMNStudent(student_cn)
                student.remove_parent(user)


for schoolclass in schoolclass_students_groups_to_update:
    lprint.info(f"Updating students group of schoolclass {schoolclass}")
    schoolclass_group = LMNSchoolclass(schoolclass)
    schoolclass_group.students_group.fill_members()

for schoolclass in schoolclass_parents_groups_to_update:
    lprint.info(f"Updating parents group of schoolclass {schoolclass}")
    schoolclass_group = LMNSchoolclass(schoolclass)
    schoolclass_group.parents_group.fill_members()

for schoolclass in schoolclass_teachers_groups_to_update:
    lprint.info(f"Updating teachers group of schoolclass {schoolclass}")
    schoolclass_group = LMNSchoolclass(schoolclass)
    schoolclass_group.teachers_group.fill_members()
