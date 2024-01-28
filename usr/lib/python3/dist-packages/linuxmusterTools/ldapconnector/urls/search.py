import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/search/(?P<query>.*)', models.LMNObject)
def global_search(query=''):
    """
    Search all cn containing the query search
    """

    if not query:
        # Get the whole menu
        return "(cn=*)"

    return f"(cn=*{query}*)"