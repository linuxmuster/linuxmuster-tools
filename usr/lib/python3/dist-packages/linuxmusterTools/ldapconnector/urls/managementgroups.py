import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER

@router.collection_s(r'/managementgroups', models.LMNGroup, subdn=f'OU=Management,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_all_groups():
    """
    Get all groups.
    Return a list of LMNGroup data objects.
    """

    ldap_filter = "(objectClass=group)"

    return ldap_filter
