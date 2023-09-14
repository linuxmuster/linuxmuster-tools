import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router

# TODO: specify school in multischool environment
@router.collection_s(r'/groups', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_all_groups():
    """
    Get all groups.
    Return a a list of LMNGroup data object.
    """

    ldap_filter = "(objectClass=group)"

    return ldap_filter

@router.single_s(r'/groups/(?P<name>[\w\-_]*)', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_group(name):
    """
    Get a group specified by its name.
    Return a a list of LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (cn={name})
                            (objectClass=group)
            )"""

    return ldap_filter