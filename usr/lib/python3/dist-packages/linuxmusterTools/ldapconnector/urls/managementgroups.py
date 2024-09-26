import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER

@router.collection(r'/managementgroups', models.LMNGroup, subdn="OU=SCHOOLS,", dn_filter=f'OU=Management,')
def get_all_management_groups():
    """
    Get all management groups.
    Return a list of LMNGroup data objects.
    """

    ldap_filter = "(objectClass=group)"

    return ldap_filter

@router.single(r'/managementgroups/(?P<name>[\w\-_]*)', models.LMNGroup, subdn="OU=SCHOOLS,", dn_filter=f'OU=Management,')
def get_management_group(name=''):
    """
    Get a management group specified by its name.
    Return a LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (cn={name})
                            (objectClass=group)
            )"""

    return ldap_filter