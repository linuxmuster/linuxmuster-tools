import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection(r'/gpos', models.LMNGPO)
def get_all_gpos():
    """
    Get all Group Policies Objects
    Return a a list of LMNGPO data object.
    """

    ldap_filter = f"""(&
                                (objectClass=groupPolicyContainer)
                            )"""

    return ldap_filter
