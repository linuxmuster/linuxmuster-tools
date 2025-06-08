#! /opt/linuxmuster/bin/python3

import os
from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNParentsGroup, LMNSchoolclass
from linuxmusterTools.common import lprint


if not os.path.isfile('/etc/linuxmuster/webui/config.yml'):
    lprint.info('New installation detected, I will not check the LDAP groups.')
else:
    try:
        # Checking groups like 7a-teachers, 7a-parents, 7a-students
        for c in lr.getval('/schoolclasses','cn'):
            lprint.info(f"Checking students groups from schoolclass {c}")
            l = LMNSchoolclass(c)
            l.fill_group_members()

        # Checking OU Student-Parents through creating a dummy LMNParentsGroup
        p = LMNParentsGroup('')
    except Exception as e:
        lprint.danger(str(e))







