import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router, SCHOOL_MARKER


@router.collection(r'/devices', models.LMNDeviceModel)
def get_all_devices():
    """
    Get all devices.
    Return a a list of LMNDeviceModel data object.
    """

    ldap_filter = f"""(&(objectClass=computer))"""

    return ldap_filter


@router.single(r'/devices/(?P<name>[\w\-]*)', models.LMNDeviceModel)
def get_device(name):
    """
    Get all details from a specific device.
    Return a LMNDeviceModel data object.
    """

    ldap_filter = f"""(&(cn={name})(objectClass=computer))"""

    return ldap_filter

@router.collection(r'/devices/search/(?P<selection>\w*)/(?P<query>[\w\-]*)', models.LMNDeviceModel)
def get_results_search_device(query, selection=[]):
    """
    Get all details from a search on a specific device scheme and having a specific role
    (something like 'printer', 'server', ...).
    Return a list of LMNDeviceModel data object.
    """


    # TODO: role filtering through selection variable must be ameliorated
    if selection == 'all':
        selection = '*'

    return f"""(&(cn=*{query}*)(objectClass=computer)(sophomorixRole={selection}))"""

@router.collection(r'/rooms', models.LMNRoomModel, subdn=f'OU=Devices,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_rooms():
    """
    Get all rooms under the Devices tree.
    """


    return f"""(&(objectClass=group)(sophomorixType=room))"""

@router.single(r'/rooms/(?P<name>[\w\-\_]*)', models.LMNRoomModel, subdn=f'OU=Devices,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_room(name):
    """
    Get a specific room under the Devices tree.
    """


    return f"""(&(cn={name})(objectClass=group)(sophomorixType=room))"""

@router.collection(r'/empty_rooms', models.LMNRoomModel, subdn=f'OU=Devices,OU={SCHOOL_MARKER},OU=SCHOOLS,')
def get_empty_rooms():
    """
    List empty rooms under the Devices tree.
    """


    # Get all devices groups under OU Devices which:
    # - contains no computer
    # - cn not starts with d_ (linbo group)
    # - not a printer

    return f"""(&(objectClass=group)(!(sophomorixRoomComputers=*))(!(cn=d_*))(!(sophomorixType=printer)))"""