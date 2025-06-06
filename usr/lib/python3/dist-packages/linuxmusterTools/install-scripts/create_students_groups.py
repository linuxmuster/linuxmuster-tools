#! /opt/linuxmuster/bin/python3

from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNParentsGroup, LMNSchoolclass
from linuxmusterTools.common import lprint


# Checking groups like 7a-teachers, 7a-parents, 7a-students
for c in lr.getval('/schoolclasses','cn'):
    lprint.info(f"Checking students groups from schoolclass {c}")
    l = LMNSchoolclass(c)
    l.fill_group_members()

# Checking OU Student-Parents through creating a dummy LMNParentsGroup
p = LMNParentsGroup('')







