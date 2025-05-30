import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection(r'/ou', models.LMNOUModel)
def get_all_ou():
    """
    Get all organizational units.
    Return a list of LMNOUModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

@router.collection(r'/ou/rooms', models.LMNOUModel, subdn=f'OU=Devices,OU={SCHOOL_MARKER},OU=SCHOOLS,', level='single')
def get_devices_ou():
    """
    Get all details from the Devices organizational unit.
    Return a LMNOUModel data object.
    """


    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

@router.collection(r'/ou/students', models.LMNOUModel, subdn=f'OU=Students,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_students_ou():
    """
    Get all details from the students organizational unit.
    Return a LMNOUModel data object.
    Quit the same as a schoolclasses request.
    """


    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter

@router.collection(r'/ou/parents', models.LMNOUModel, subdn=f'OU=Parents,OU={SCHOOL_MARKER},OU=SCHOOLS,', level='single')
def get_students_parents_ou():
    """
    Get all details from all OU in parents OU organizational unit.
    Return a LMNOUModel data object.
    """


    ldap_filter = f"""(&
                                (objectClass=organizationalUnit)
                            )"""

    return ldap_filter