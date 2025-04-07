from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNUserWriter
from linuxmusterTools.common import lprint


uw = LMNUserWriter()

# First check: each student has a parent group
students = lr.getval('/roles/student', 'cn')
count = len(students)
orphan_student_cn = []

for idx, student in enumerate(students):
    parent_group = uw.get_parent_group(student)
    if not parent_group:
        orphan_student_cn.append(student)
    print(f"First pass: checking parent group of existing student {idx+1:>4} of {count}", end="\r")

print()

# Create missing parents groups
if orphan_student_cn:
    print("Creating missing parents group ...")
    for student in orphan_student_cn:
        uw.add_parent_group(student)
        lprint.info(f"Missing parent group for {student} created!")
else:
    lprint.success("Checks done, everything is alright!")

orphan_parent_dn = []

# Second check: each parent group is associated to a real student in the same OU
parent_groups = lr.get('/search/-parents', attributes=['cn', 'dn'])
count = len(parent_groups)

for idx, group in enumerate(parent_groups):
    cn = group['cn']
    dn = group['dn']

    # Ignore global groups
    if cn in ['all-parents', 'global-parents']:
        continue

    parentgroup_schoolclass = dn.split(',')[1].split('=')[1]
    student = cn.split('-')[0]
    student_data = lr.get(f"/users/{student}")
    if not student_data or parentgroup_schoolclass != student_data['sophomorixAdminClass']:
        orphan_parent_dn.append(dn)
    print(f"Second pass: checking existing parent group {idx+1:>4} of {count}", end="\r")

print()

# Delete orphan parents groups
if orphan_parent_dn:
    print("Deleting obsolete parents group ...")
    for parent in orphan_parent_dn:
        uw.del_parent_group_per_dn(parent)
        lprint.info(f"Obsolete parent group {parent} deleted!")
else:
    lprint.success("Checks done, everything is alright!")

