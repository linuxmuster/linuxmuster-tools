import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/roles/(?P<role>.*)', models.LMNUser)
def get_all_from_role(role='teacher'):
    """
    Get all user from a same role.
    Return a list of LMNUser data objects.
    """

    return f"(&(objectClass=user)(sophomorixRole={role}))"