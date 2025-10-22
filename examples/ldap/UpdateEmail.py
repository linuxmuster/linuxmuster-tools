#! /usr/bin/env python3

"""
Script to update all teacher's email addresses in the attribute mail
with the template lastname-firstname@mydomain.school.
You can replace the email in the attribute proxyAddresse through the same way.
In order to keep all teacher's email up-to-date, you can put this script in
/etc/linuxmuster/sophomorix/default-school/hooks/sophomorix-update.d and in
/etc/linuxmuster/sophomorix/default-school/hooks/sophomorix-add.d

(this will be executed after each sophomorix user's change in Ldap).
"""

from linuxmusterTools.ldapconnector import LMNTeachers

# Get a list of all teachers, but with write permissions in Ldap!
# Be careful to not change attributes if you not know what you are doing.

teachers = LMNTeachers()

domain = "mydomain.school"

# Email template lastname-firstname@mydomain.school
for cn, teacher in teachers.items():

    # Shortcut for all teacher's data
    data = teacher.data
    lastname = data['sn'].lower()
    firstname = data['displayName'].lower()

    # Prepare a new email like lastname-firstname@mydomain.school
    new_mail = f"{lastname}-{firstname}@{domain}"

    # Save in LDAP
    teacher.setattr(data={'mail': new_mail})

