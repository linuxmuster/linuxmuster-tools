import ldap.filter
import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/roles/(?P<role>.*)', models.LMNUserModel)
def get_all_from_role(role='teacher'):
    """
    Get all user from a same role.
    Return a list of LMNUserModel data objects.
    """

    role = ldap.filter.escape_filter_chars(role)
    return f"(&(objectClass=user)(sophomorixRole={role}))"

@router.collection(r'/rawroles/(?P<role>.*)', models.LMNRawUserModel)
def get_all_raw_from_role(role='teacher'):
    """
    Get all user from a same role, but in this case without parents / children request.
    Return a list of LMNRawUserModel data objects.
    """

    role = ldap.filter.escape_filter_chars(role)
    return f"(&(objectClass=user)(sophomorixRole={role}))"
