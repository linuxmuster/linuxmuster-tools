#! /usr/bin/env python3

"""
Given a CSV containing all lastnames, firstnames and schoolclass memberships from all teachers, script to update
all teacher memberships (Kürzel) in the schoolclasses.


The CSV should looks like:
FIRSTNAME;LASTNAME;SCHOOLCLASS1,SCHOOLCLASS2...;etc...
Abel;Anatole;5a,10a,12b
Abel;Bertha;8c,9b
Antolin;Christian;10a,10b
...
"""


import csv
from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNSchoolclasses
from linuxmusterTools.common import lprint


# Get a list of all teachers
# (only the attributes cn, givenName and sn - 
# to get a list of all teachers with all attributes, just use
# lr.get('/roles/teachers')

teachers = lr.get('/roles/teacher', attributes=['cn', 'givenName', 'sn'])

# Loading a dict containing all schoolclasses objects and subgroups (teachers, students, parents)
# Loading all this stuff may be long
schoolclasses = LMNSchoolclasses()

# Beware, this will remove all teachers memberships in all schoolclasses !
# All subgroups SCHOOLCLASS-teachers will be updated too
for schoolclass in schoolclasses:
    schoolclass.remove_all_teachers()

## CSV like FIRSTNAME;LASTNAME;SCHOOLCLASS1,SCHOOLCLASS2...;etc...
with open('MYCSV.csv','r') as f:
    teacher_csv = csv.reader(f, delimiter=';')
    for entry in teacher_csv:
        
        csvname = f"{entry[0].lower()};{entry[1].lower()}"
        code = entry[2]
        
        for teacher in teachers:
            ldapname = f"{teacher['sn'].lower()};{teacher['givenName'].lower()}"
            # Matching teachers
            if ldapname == csvname:
                teacher_schoolclasses = entry[3].split(',')

                for schoolclass in teacher_schoolclasses:
                    # A typo may happen, checking that the schoolclass code really exists
                    if schoolclass in schoolclasses.keys():
                        # Adding teacher as member
                        # Subgroup SCHOOLCLASS-teachers will be automatically updated too
                        schoolclasses[schoolclass].add_member(teacher['cn'])

                    # Print a red message if not
                    else:
                        lprint.danger(f"Schoolclass {schoolclass} not found for teacher {teacher['cn']}!")

        else:
            # Print an orange warning
            lprint.warning(f"Teacher {csvname} not found.")


