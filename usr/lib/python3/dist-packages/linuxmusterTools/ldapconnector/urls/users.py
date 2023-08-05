import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/users', models.LMNUser)
def get_all_users():
    pass


@router.single(r'/users/(?P<username>[\w\-]*)', models.LMNUser)
def get_user(username):
    """
    Get all details from a specific user.
    Return a LMNUser data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/users/search/(?P<selection>\w*)/(?P<query>\w*)', models.LMNUser)
def get_results_search_user(query, selection=[]):
    """
    Get all details from a search on a specific user login scheme and a
    selection of roles.
    Return a list of LMNUser data object.
    """

    role_filter = {
        'all': """
                (sophomorixRole=globaladministrator)
                (sophomorixRole=schooladministrator)
                (sophomorixRole=teacher)
                (sophomorixRole=student)
            """,
        'admins': """
                (sophomorixRole=globaladministrator)
                (sophomorixRole=schooladministrator)
            """,
    }

    for role in ['globaladministrator', 'schooladministrator', 'teacher', 'student']:
        role_filter[role] = f'(sophomorixRole={role})'

    return f"""(&
                                (sAMAccountName=*{query}*)
                                (objectClass=user)
                                (|
                                    {role_filter[selection]}
                                )
                            )"""
