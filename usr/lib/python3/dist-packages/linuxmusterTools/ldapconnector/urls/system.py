import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection(r'/gpos', models.LMNGPO)
def get_all_gpos():
    """
    Get all Group Policies Objects
    Return a list of LMNGPO data object.
    """

    ldap_filter = f"""(&
                                (objectClass=groupPolicyContainer)
                            )"""

    return ldap_filter

@router.single(r'/gpos/(?P<name>[\w\-_: ]*)', models.LMNGPO)
def get_one_gpo(name):
    """
    Get one specific Group Policy Object after his displayName
    Return a LMNGPO data object.
    """

    ldap_filter = f"""(&
                                (objectClass=groupPolicyContainer)
                                (displayName={name})
                            )"""

    return ldap_filter