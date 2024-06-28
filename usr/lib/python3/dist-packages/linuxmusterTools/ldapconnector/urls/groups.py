import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection_s(r'/units', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_all_units():
    """
    Get all units. The terminology "unit" was chosen in order to differenciate with a "group" from
    sophomorix-group. A unit can be a schoolclass, a project, a group, etc ...
    Return a list of LMNGroup data objects.
    """

    ldap_filter = "(objectClass=group)"

    return ldap_filter

@router.single_s(r'/units/(?P<name>[\w\-_]*)', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_group(name=''):
    """
    Get a unit specified by its name. The terminology "unit" was chosen in order to differenciate with a "group" from
    sophomorix-group. A unit can be a schoolclass, a project, a group, etc ...
    Return a LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (cn={name})
                            (objectClass=group)
            )"""

    return ldap_filter


@router.collection_s(r'/groups', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_all_groups():
    """
    Get all groups (meaning units with sophomorixType sophomorix-group).
    Return a list of LMNGroup data objects.
    """

    ldap_filter = f"""(&
                            (sophomorixType=sophomorix-group)
                            (objectClass=group)
            )"""

    return ldap_filter

@router.single_s(r'/groups/(?P<name>[\w\-_]*)', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_group(name=''):
    """
    Get a group (meaning units with sophomorixType sophomorix-group) specified by its name.
    Return a LMNGroup data object.
    """

    ldap_filter = f"""(&
                            (cn={name})
                            (sophomorixType=sophomorix-group)
                            (objectClass=group)
            )"""

    return ldap_filter

@router.collection_s(r'/printers', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
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

@router.single_s(r'/printers/(?P<name>[\w\-_]*)', models.LMNGroup, subdn=f'OU={SCHOOL_MARKER},OU=SCHOOLS,')
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
