import ldap.filter
import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/users', models.LMNUserModel)
def get_all_users():
    """
    Get all details from all users.
    Return a list of LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/users/exam', models.LMNUserModel)
def get_exam_users():
    """
    Get all details from all users in exam mode.
    Return a LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=examuser)
                                )
                            )"""

    return ldap_filter

@router.single(r'/users/exam/(?P<username>[\w\-]*)', models.LMNUserModel)
def get_exam_user(username):
    """
    Get all details from a specific user in exam mode.
    Return a LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (|(cn={username})(cn={username}-exam))
                                (objectClass=user)
                                (|
                                    (sophomorixRole=examuser)
                                )
                            )"""

    return ldap_filter

@router.single(r'/users/(?P<username>[\w\-]*)', models.LMNUserModel)
def get_user(username):
    """
    Get all details from a specific user.
    Return a LMNUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/users/search/(?P<selection>\w*)/(?P<query>[\w\+]*)', models.LMNUserModel)
def get_results_search_user(query='', selection=[]):
    """
    Get all details from a search on a specific user login scheme and a
    selection of roles.
    Return a list of LMNUserModel data object.
    """

    role_filter = {
        'all': """
                (sophomorixRole=globaladministrator)
                (sophomorixRole=schooladministrator)
                (sophomorixRole=teacher)
                (sophomorixRole=student)
                (sophomorixRole=parent)
                (sophomorixRole=staff)
            """,
        'admins': """
                (sophomorixRole=globaladministrator)
                (sophomorixRole=schooladministrator)
            """,
    }

    for role in ['globaladministrator', 'schooladministrator', 'teacher', 'student', 'parent']:
        role_filter[role] = f'(sophomorixRole={role})'

    if query:
        query = ldap.filter.escape_filter_chars(query)
        query = f"(|(sAMAccountName=*{query}*)(sn=*{query}*)(givenName=*{query}*))"

    return f"""(&
                                {query}
                                (objectClass=user)
                                (|
                                    {role_filter[selection]}
                                )
                            )"""

@router.collection(r'/rawusers', models.LMNRawUserModel)
def get_all_raw_users():
    """
    Get all details from all users.
    Return a list of LMNRawUserModel data object.
    """

    ldap_filter = f"""(&
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter

@router.single(r'/rawusers/(?P<username>[\w\-]*)', models.LMNRawUserModel)
def get_raw_user(username):
    """
    Get all details from a specific user.
    Return a LMNRawUserModel data object.
    """

    ldap_filter = f"""(&
                                (cn={username})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/batch_rawusers/(?P<usernames>[\w\-,]*)', models.LMNRawUserModel)
def get_batch_raw_users(usernames):
    """
    Get all details from specific users: usernames should be a comma-separated
    list of valid sAMAccountNames.
    Return a list of LMNRawUserModel data object.
    """


    cn_list = usernames.split(',')
    selector = ''.join([f"(cn={ldap.filter.escape_filter_chars(cn)})" for cn in cn_list])

    ldap_filter = f"""(&
                                (|{selector})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter

@router.collection(r'/batch_users/(?P<usernames>[\w\-,]*)', models.LMNUserModel)
def get_batch_users(usernames):
    """
    Get all details from specific users: usernames should be a comma-separated
    list of valid sAMAccountNames.
    Return a list of LMNRawUserModel data object.
    """


    cn_list = usernames.split(',')
    selector = ''.join([f"(cn={ldap.filter.escape_filter_chars(cn)})" for cn in cn_list])

    ldap_filter = f"""(&
                                (|{selector})
                                (objectClass=user)
                                (|
                                    (sophomorixRole=globaladministrator)
                                    (sophomorixRole=schooladministrator)
                                    (sophomorixRole=teacher)
                                    (sophomorixRole=student)
                                    (sophomorixRole=parent)
                                    (sophomorixRole=staff)
                                )
                            )"""

    return ldap_filter
