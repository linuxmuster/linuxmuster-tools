import logging

from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from linuxmusterTools.lmnconfig import SAMBA_REALM


def check_empty_ou_rooms():
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


def check_devices():
    """
    Check if devices attributes are consistent.

    :return:
    :rtype:
    """


    devices = lr.get('/devices')

    report = {}

    for device in devices:

        if "Domain Controllers" in device['dn']:
            # Not checking domain controllers
            continue

        error = False

        cn = device['cn']
        report[cn] = []

        if device['sophomorixSchoolname'] != 'default-school':
            schoolprefix = f"{device['sophomorixSchoolname']}."
            if device['sophomorixSchoolname'] != device['sophomorixSchoolPrefix']:
                error = True
                report[cn].append(f"sophomorixSchoolname and sophomorixSchoolPrefix are different ({device['sophomorixSchoolname']} != {device['sophomorixSchoolPrefix']}")
        else:
            schoolprefix = ''
            if device['sophomorixSchoolPrefix'] != '---':
                error = True
                report[cn].append(f"sophomorixSchoolPrefix should be '---'")

        ou = [node.split("=") for node in device['dn'].split(',')][1][1]
        ou_group = device['dn'].replace(f"CN={cn}", f"CN={ou}")

        # Check dNS
        if device['dNSHostName'] != f'{cn}.{SAMBA_REALM}':
            error = True
            report[cn].append(f"dNSHotName should be {f'{cn}.{SAMBA_REALM}'} and not {device['dNSHostName']}")

        # Check name
        if device['name'] != cn:
            error = True
            report[cn].append(f"name should be {cn} and not {device['name']}")

        # Check memberOf
        # TODO: missing tests
        if ou_group not in device['memberOf']:
            error = True
            report[cn].append(f"memberOf should contain {ou_group}")

        # Check sAMAccountName
        if device['sAMAccountName'] != f'{cn}$':
            error = True
            report[cn].append(f"sAMAccountName should be {cn} and not {device['sAMAccountName']}")

        # Check servicePrincipalName
        if f"HOST/{cn}" not in device["servicePrincipalName"]:
            error = True
            report[cn].append(f"servicePrincipalName should contain {f'HOST/{cn}'}")
        if f"HOST/{cn}.{SAMBA_REALM}" not in device["servicePrincipalName"]:
            error = True
            report[cn].append(f"servicePrincipalName should contain {f'HOST/{cn}.{SAMBA_REALM}'}")
        if f"RestrictedKrbHost/{cn}" not in device["servicePrincipalName"]:
            error = True
            report[cn].append(f"servicePrincipalName should contain {f'RestrictedKrbHost/{cn}'}")
        if f"RestrictedKrbHost/{cn}.{SAMBA_REALM}" not in device["servicePrincipalName"]:
            error = True
            report[cn].append(f"servicePrincipalName should contain {f'RestrictedKrbHost/{cn}.{SAMBA_REALM}'}")

        # Check sophomorix attributes
        if device['sophomorixAdminClass'] != ou:
            error = True
            report[cn].append(f"sophomorixAdminClass should be {ou}")
        if device['sophomorixComputerRoom'] != ou:
            error = True
            report[cn].append(f"sophomorixComputerRoom should be {ou}")
        if device['sophomorixDnsNodename'] != cn.lower():
            error = True
            report[cn].append(f"sophomorixDnsNodename should be {cn.lower()}")
        if device['sophomorixAdminFile'] != f"{schoolprefix}devices.csv":
            error = True
            report[cn].append(f"ophomorixAdminFile should be {f'{schoolprefix}devices.csv'}")

        if not error:
            del report[cn]

    return report