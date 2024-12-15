import logging

from linuxmusterTools.ldapconnector import LMNLdapReader as lr


def empty_ou_rooms():
    """
    List all organizational units in devices which have no associated group and
    no devices.

    :return:
    :rtype:
    """

    rooms = lr.get('/ou/devices')

    for r in rooms:
        group = lr.get(f'/rooms/{r["name"]}')
        if not group:

            # Check if there are still devices in this OU
            orphan_devices = []
            for device in lr.get(f'/devices', attributes=['dn', 'name']):
                if r['dn'] in device['dn']:
                    orphan_devices.append(device['name'])

            if orphan_devices:
                devices = " / ".join(orphan_devices)
                logging.error(f"Room {r['name']} doesn't have an associated group and contains {devices}.")
            else:
                logging.warning(f"Room {r['name']} doesn't have an associated group.")
        elif len(group['member']) == 0:
            logging.warning(f"Room {r['name']} doesn't contain any device.")
