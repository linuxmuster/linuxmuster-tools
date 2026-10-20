#! /usr/bin/env python3

"""
Script to provide an CSV export for Koha (only teachers and students)

Output file is /var/lib/lmntools/print/koha_export.csv and looks like:

surname;firstname;branchcode;categorycode;auth_method;userid;patron_attributes;
Müller;Malte;My Gymnasium;ST;ldap;muellma;Klasse:5e;
Müller;Holger;my Gymnasium;ST;ldap;muellho;Klasse:teachers;
"""


from linuxmusterTools.ldapconnector import LMNTeachers, LMNStudents

content = "surname;firstname;branchcode;categorycode;auth_method;userid;patron_attributes;\n"

BRANCHCODE = "My SCHOOL"
CATEGORYCODE = "My CATEGORY"
AUTH_METHOD = "ldap"
PATRON = "Klasse"

OUTPUT_FILE = "/var/lib/lmntools/print/koha_export.csv"

users = {**LMNTeachers().teachers, **LMNStudents().students}

for cn, user in users.items():
    data = user.data
    content += f"{data['sn']};{data['givenName']};{BRANCHCODE};{CATEGORYCODE};{AUTH_METHOD};{data['cn']};{PATRON}:{data['sophomorixAdminClass']};\n"


with open(OUTPUT_FILE,'w') as f:
    f.write(content)


