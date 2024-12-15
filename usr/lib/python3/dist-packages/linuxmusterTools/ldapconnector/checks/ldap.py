import logging

from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from linuxmusterTools.lmnconfig import SAMBA_REALM


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


def devices():
    """
    Check if devices attributes are consistent.

    :return:
    :rtype:
    """


    devices = lr.get('/devices')

    for device in devices:
        cn = device['cn']
        ou = [node.split("=") for node in device['dn'].split(',')][1][1]
        ou_group = device['dn'].replace(f"CN={cn}", f"CN={ou}")

        try:
            # Check dNS
            assert device['dNSHostName'] == f'{cn}.{SAMBA_REALM}'

            # Check name
            assert device['name'] == cn

            # Check memberOf
            # TODO: missing tests
            assert ou_group in device['memberOf']

            # Check sAMAccountName
            assert device['sAMAccountName'] == f'{cn}$'

            # Check servicePrincipalName
            assert f"HOST/{cn}" in device["servicePrincipalName"]
            assert f"HOST/{cn}.{SAMBA_REALM}" in device["servicePrincipalName"]
            assert f"RestrictedKrbHost/{cn}" in device["servicePrincipalName"]
            assert f"RestrictedKrbHost/{cn}.{SAMBA_REALM}" in device["servicePrincipalName"]

            # Check sophomorix attributes
            assert device['sophomorixAdminClass'] == ou
            assert device['sophomorixComputerRoom'] == ou
            assert device['sophomorixDnsNodename'] == cn.lower()
            assert device['sophomorixAdminFile'] == "devices.csv" # Ok for multischool ?

        except AssertionError as e:
            print(device)
            raise
