#! /opt/linuxmuster/bin/python3

from pathlib import Path

from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNParentsGroup, LMNSchoolclass
from linuxmusterTools.common import lprint


if not Path('/etc/linuxmuster/webui/config.yml').is_file():
    lprint.info('New installation detected, I will not check the LDAP groups.')
else:
    # Checking groups like 7a-teachers, 7a-parents, 7a-students.
    # No school given on purpose: every schoolclass of every school must be
    # checked here, and each one carries its own sophomorixSchoolname.
    for c in lr.get('/schoolclasses', as_dict=False):
        # The attic is an adminclass too, but has no students/teachers/parents
        # subgroups to maintain. Filtering on the dn and not on the cn, which
        # is prefixed with the school name in a multischool setup.
        if ',OU=attic,' in c.dn:
            continue

        lprint.info(f"Checking students groups from schoolclass {c.cn}")
        try:
            l = LMNSchoolclass(c.cn, school=c.sophomorixSchoolname)
            l.fill_group_members()
        except Exception as e:
            # A single broken schoolclass must not skip all the following ones
            lprint.danger(f"Could not check the groups of schoolclass {c.cn}: {str(e)}")

    # Checking OU Student-Parents through creating a dummy LMNParentsGroup
    for school in lr.getval('/schools', 'ou'):
        try:
            p = LMNParentsGroup('', school=school)
        except Exception as e:
            lprint.danger(f"Could not check the Student-Parents OU of {school}: {str(e)}")
