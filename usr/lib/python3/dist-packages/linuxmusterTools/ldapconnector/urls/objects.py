import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.single(r'/dn/(?P<dn>.*)', models.LMNObjectModel)
def get_from_dn(dn):
    """
    Search for a specific dn and retrieve a common LMNObjectModel from it.
    """

    ldap_filter = f"""(distinguishedName={dn})"""

    return ldap_filter