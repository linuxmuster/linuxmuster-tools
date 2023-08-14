import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/devices', models.LMNDevice)
def get_all_devices():
    """
    Get all devices.
    Return a a list of LMNDevice data object.
    """

    ldap_filter = f"""(&
                                (objectClass=computer)
                            )"""

    return ldap_filter


@router.single(r'/devices/(?P<name>[\w\-]*)', models.LMNDevice)
def get_device(name):
    """
    Get all details from a specific device.
    Return a LMNDevice data object.
    """

    ldap_filter = f"""(&
                                (cn={name})
                                (objectClass=computer)
                            )"""

    return ldap_filter

@router.collection(r'/devices/search/(?P<selection>\w*)/(?P<query>[\w\-]*)', models.LMNDevice)
def get_results_search_device(query):
    """
    Get all details from a search on a specific device scheme
    Return a list of LMNDevice data object.
    """

    return f"""(&
                                (cn=*{query}*)
                                (objectClass=computer)
                            )"""
