import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/globaladministrators', models.LMNUserModel)
def get_all_globaladministrators():
    """
    Get all details from all globaladministrators.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                )
                            )"""

    return ldap_filter

@router.single(r'/globaladministrators/(?P<username>[\w\-]*)', models.LMNUserModel)
def get_globaladministrator(username):
    """
    Get all details from a specific globaladministrator.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/schooladministrators', models.LMNUserModel)
def get_all_schooladministrators():
    """
    Get all details from all schooladministrators.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=schooladministrator)
                                )
                            )"""

    return ldap_filter

@router.single(r'/schooladministrators/(?P<username>[\w\-]*)', models.LMNUserModel)
def get_schooladministrator(username):
    """
    Get all details from a specific schooladministrator.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=schooladministrator)
                                )
                            )"""

    return ldap_filter

