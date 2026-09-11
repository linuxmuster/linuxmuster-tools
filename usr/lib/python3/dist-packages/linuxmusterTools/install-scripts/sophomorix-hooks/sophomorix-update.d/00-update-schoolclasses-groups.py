#! /usr/bin/env python3

# This script is part of the sophomorix project and intended to update
# CN of parents groups in students OU for students which attributes changed.
# DO NOT EDIT OR REMOVE IT !


import sys
from linuxmusterTools.common import lprint, parse_update_log
from linuxmusterTools.ldapconnector import LMNUser, LMNSchoolclass, LMNStudent


# sophomorix also passes the school as second argument, but it is not
# used: the sophomorix logs are global files and carry the school of
# every entry, so one copy of this hook handles all the schools.
epoch = sys.argv[1]

if epoch is None:
    updates = parse_update_log(today=True)
    timestamps = list(updates.keys())
    timestamps.sort()
    epoch = timestamps[-1]
    entries = updates[epoch]
else:
    entries = parse_update_log(epoch=epoch)

schoolclass_groups_to_update = {
    'default-school': {
        'students': set(),
        'teachers': set(),
        'parents': set()
    }
}

for entry in entries:
    user = entry["user"]
    changes = entry["changes"]
    school = entry["school"]

    if school not in schoolclass_groups_to_update:
        schoolclass_groups_to_update[school] = {
            'students': set(),
            'teachers': set(),
            'parents': set()
        }

    if 'group' in changes:
        old_group, new_group = changes['group'].split('->')
        old_role, new_role = changes['role'].split('->')

        if old_role == new_role == 'student':

            # Student moving from a schoolclass to another, eventually attic

            if old_group != 'attic':
                # Removing student / student's parents from old students / parents group
                schoolclass_groups_to_update[school]['students'].add(old_group)
                schoolclass_groups_to_update[school]['parents'].add(old_group)

            if new_group == 'attic':
                # Delete CN in Student-Parents
                student = LMNStudent(user)
                student.parents_group.delete()

            else:
                # Adding student / student's parents to new students / parents group
                schoolclass_groups_to_update[school]['students'].add(new_group)
                schoolclass_groups_to_update[school]['parents'].add(new_group)

        elif old_group == 'teachers' and new_group == 'attic':

            # Teacher moves to attic to be deleted. It's necessary to remove this
            # teacher from all teachers groups

            teacher = LMNUser(user)
            for c in teacher.data['schoolclasses']:
                schoolclass_groups_to_update[school]['teachers'].add(c)

        elif old_group == 'parents' and new_group == 'attic':

            # Parent moves to attic to be deleted.

            parent = LMNUser(user)
            parent.get_children()

            # Remove parent from all parents groups in students
            for schoolclass in parent.children_schoolclasses:
                schoolclass_groups_to_update[school]['parents'].add(schoolclass)

            # Remove parent from Student-Parents' entries
            for student_cn in parent.children_cn:
                student = LMNStudent(student_cn)
                student.remove_parent(user)

for school, groups in schoolclass_groups_to_update.items():
    for group_type in ['students', 'parents', 'teachers']:
        for schoolclass in groups[group_type]:
            lprint.lmn(f"Updating {group_type} group of schoolclass {schoolclass} in {school}")
            try:
                schoolclass_group = LMNSchoolclass(schoolclass, school=school)
                getattr(schoolclass_group, f'{group_type}_group').fill_members()
            except Exception as e:
                # A single failing schoolclass must not abort the whole hook:
                # the users have already been updated by sophomorix at this
                # point.
                lprint.danger(f"Could not update the {group_type} group of {schoolclass} in {school}: {str(e)}")
