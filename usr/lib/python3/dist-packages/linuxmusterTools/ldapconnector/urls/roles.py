import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/roles/(?P<role>.*)', models.LMNUserModel)
def get_all_from_role(role='teacher'):
    """
    Get all user from a same role.
    Return a list of LMNUserModel data objects.
    """

    return f"(&(objectClass=user)(sophomorixRole={role}))"