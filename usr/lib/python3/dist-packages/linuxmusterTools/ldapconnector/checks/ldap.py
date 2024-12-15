import logging

from linuxmusterTools.ldapconnector import LMNLdapReader as lr


def empty_ou_rooms():
    """
    List all organizational units in devices which have no associated group and
    no devices.

    :return: Report with list of error types
    :rtype: dict
    """

    rooms = lr.get('/ou/devices')

    report = {
        'NO_CN':[],
        'NO_CN_WITH_DEVICES':[],
        'NO_DEVICES':[]
    }

    for r in rooms:
        group = lr.get(f'/rooms/{r["name"]}')
        if not group:

            # Check if there are still devices in this OU
            orphan_devices = []
            for device in lr.get(f'/devices', attributes=['dn', 'name']):
                if r['dn'] in device['dn']:
                    orphan_devices.append(device['name'])

            if orphan_devices:
                report['NO_CN_WITH_DEVICES'].append(r['name'])
                devices = " / ".join(orphan_devices)
                logging.error(f"Room {r['name']} doesn't have an associated group and contains {devices}.")
            else:
                report['NO_CN'].append(r['name'])
                logging.warning(f"Room {r['name']} doesn't have an associated group.")
        elif len(group['member']) == 0:
            report['NO_DEVICES'].append(r['name'])
            logging.warning(f"Room {r['name']} doesn't contain any device.")

    return report
