import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/globalbindusers', models.LMNUserModel)
def get_all_globalbindusers():
    """
    Get all details from all globalbindusers.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globalbinduser)
                                )
                            )"""

    return ldap_filter

@router.single(r'/globalbindusers/(?P<username>[\w\-.]*)', models.LMNUserModel)
def get_globalbinduser(username):
    """
    Get all details from a specific globalbinduser.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globalbinduser)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/schoolbindusers', models.LMNUserModel)
def get_all_schoolbindusers():
    """
    Get all details from all schoolbindusers.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=schoolbinduser)
                                )
                            )"""

    return ldap_filter

@router.single(r'/schoolbindusers/(?P<username>[\w\-.]*)', models.LMNUserModel)
def get_schoolbinduser(username):
    """
    Get all details from a specific schoolbinduser.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=schoolbinduser)
                                )
                            )"""

    return ldap_filter

