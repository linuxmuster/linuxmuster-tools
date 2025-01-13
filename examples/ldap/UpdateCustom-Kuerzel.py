#! /usr/bin/env python3

"""
Given a CSV containing all lastnames, firstnames and codes from all teachers, script to update 
all "teacher codes" (Kürzel) in the attribute sophomorixCustom1 and subjects in sophomorixCustomMulti1.
"""

import csv
from linuxmusterTools.ldapconnector import LMNLdapReader as lr, UserWriter as uw
from linuxmusterTools.quotas import get_user_quotas


# Get a list of all teachers
# (only the attributes cn, givenName and sn - 
# to get a list of all teachers with all attributes, just use
# lr.get('/roles/teachers')

teachers = lr.get('/roles/teacher', attributes=['cn', 'givenName', 'sn'])

## CSV like FIRSTNAME;LASTNAME;CODE;SUBJECT1,SUBJECT2...;etc...
with open('MYCSV.csv','r') as f:
    teacher_csv = csv.reader(f, delimiter=';')
    for entry in teacher_csv:
        
        csvname = f"{entry[0].lower()};{entry[1].lower()}"
        code = entry[2]
        
        for teacher in teachers:
            ldapname = f"{teacher['sn'].lower()};{teacher['givenName'].lower()}"
            # Matching teachers
            if ldapname == csvname:
                subjects = entry[3].split(',')
                
                # Write new data for code and subjects
                uw.setattr(teacher['cn'], data={'sophomorixCustom1':code, 'sophomorixCustomMulti1':subjects})
                
                # Update the LMNQuota too
                quotas = get_user_quotas(teacher['cn'])['default-school']
                uw.setattr(teacher['cn'], data={'sophomorixCustom2': f"{quotas['hard_limit']};{quotas['used']}"})
                break
        else:
            print(f"Teacher {csvname} not found.")


