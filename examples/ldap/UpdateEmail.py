#! /usr/bin/env python3

"""
Script to update all email addresses in the attribute proxyAddresses
with the template lastname-firstname@mydomain.school.
"""

from linuxmusterTools.ldapconnector import LMNLdapReader as lr, UserWriter as uw

# Get a list of all teachers
# (only the attributes cn, givenName and sn - 
# to get a list of all teachers with all attributes, just use
# lr.get('/roles/teachers')

teachers = lr.get('/roles/teacher', attributes=['cn', 'givenName', 'sn'])

domain = "mydomain.school"

# Email template lastname-firstname@mydomain.school
for teacher in teachers:
    email = f"{teacher['sn']}-{teacher['givenName']}@{domain}"
    uw.setattr(teacher['cn'], data={'proxyAddresses':email})

