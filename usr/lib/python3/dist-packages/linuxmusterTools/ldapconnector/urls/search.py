import ldap.filter

import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/search/(?P<query>.*)', models.LMNObjectModel)
def global_search(query=''):
    """
    Search all cn containing the query search.
    """

    if not query:
        # Get the whole menu
        return "(cn=*)"

    query = ldap.filter.escape_filter_chars(query)

    return f"""(
                |
                (cn=*{query}*)
                (ou=*{query}*)
                (displayName=*{query}*)
    )"""
