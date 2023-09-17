import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router

# TODO: specify school in multischool environment
@router.collection_s(r'/groups', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_all_groups():
    """
    Get all groups.
    Return a list of LMNGroup data objects.
    """

    ldap_filter = "(objectClass=group)"

    return ldap_filter

@router.single_s(r'/groups/(?P<name>[\w\-_]*)', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_group(name=''):
    """
    Get a group specified by its name.
    Return a LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (cn={name})
                            (objectClass=group)
            )"""

    return ldap_filter

@router.collection_s(r'/printers', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_all_printers():
    """
    Get all printer groups.
    Return a list of LMNGroup data objects.
    """

    ldap_filter = f"""(&
                            (sophomorixType=printer)
                            (objectClass=group)
            )"""

    return ldap_filter

@router.single_s(r'/printers/(?P<name>[\w\-_]*)', models.LMNGroup, subdn='OU=default-school,OU=SCHOOLS,')
def get_printer(name=''):
    """
    Get a specific printer.
    Return a LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (sophomorixType=printer)
                            (cn={name})
                            (objectClass=group)
            )"""

    return ldap_filter
