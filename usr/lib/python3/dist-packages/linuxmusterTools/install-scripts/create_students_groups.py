#! /opt/linuxmuster/bin/python3

"""
DEPRECATED - kept for manual use only, nothing calls it any more.

debian/postinst used to run this on every install and upgrade, sweeping every
schoolclass of every school. That sweep is now redundant: the subgroups of a
class are maintained in line by the sophomorix-add/-update hooks, and by the
lmncli callback sophomorix-class makes on --addadmins/--removeadmins and
--addmembers/--removemembers (sophomorix4 >= 7.4.4). It was also slow and it
failed the whole package configuration whenever LDAP was down.

To repair a class that drifted anyway - a direct LDAP edit, a hook that failed -
use the on demand command instead:

    lmncli schoolclass sync -c <class> -s <school> --groups

The sweep this script used to do at every upgrade has an exact equivalent, to
run by hand when it is actually wanted:

    lmncli schoolclass sync --all -s <school>

Note that the second half of this script never worked: LMNParentsGroup('')
reaches _check_ou() before self.student is set, so it raises AttributeError in
the very case it was meant to fix - an actually missing Student-Parents OU.
That OU is created on demand by any real LMNParentsGroup(<student>) anyway.

May be removed in a future release.
"""


from pathlib import Path

from linuxmusterTools.ldapconnector import LMNLdapReader as lr, LMNParentsGroup, LMNSchoolclass
from linuxmusterTools.common import lprint


lprint.warning(
    'This script is deprecated and no longer run by the package. '
    'Use "lmncli schoolclass sync" to repair a schoolclass.'
)

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
