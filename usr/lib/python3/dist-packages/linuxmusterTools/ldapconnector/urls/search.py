import ldap.filter

import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/search/(?P<query>.*)', models.LMNObject)
def global_search(query=''):
    """
    Search all cn containing the query search
    """

    return f"(cn=*{query}*)"