import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection(r'/ou', models.LMNOU)
def get_all_ou():
    """
    Get all organizational units.
    Return a a list of LMNOU data object.
    """

    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

@router.collection(r'/ou/devices', models.LMNOU, subdn=f'OU=Devices,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_devices_ou():
    """
    Get all details from the devices organizational unit.
    Return a LMNOU data object.
    """

    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

@router.collection(r'/ou/students', models.LMNOU, subdn=f'OU=Students,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_students_ou():
    """
    Get all details from the students organizational unit.
    Return a LMNOU data object.
    Quit the same as a schoolclasses request.
    """

    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

