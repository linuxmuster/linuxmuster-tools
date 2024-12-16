import ldap
import logging
from dataclasses import fields

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from .object import LMNObjectWriter
from ..models import LMNRoom
from linuxmusterTools.common import Validator
from linuxmusterTools.lmnconfig import LDAP_CONTEXT


class LMNDeviceWriter:

    def __init__(self):
        self.lw = LdapWriter()
        self.lr = router
        self.ow = LMNObjectWriter()

    def setattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.info(f"The device {name} was not found in ldap.")
            raise Exception(f"The device {name} was not found in ldap.")

        self.lw._setattr(details, **kwargs)

    def delattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.info(f"The device {name} was not found in ldap.")
            raise Exception(f"The device {name} was not found in ldap.")

        self.lw._delattr(details, **kwargs)

    def rename(self, name, new_name):
        """
        Rename a device inside a room.

        :param new_name:
        :type new_name:
        :return:
        :rtype:
        """


        if not Validator.check_host_name(new_name):
            logging.error(f"{new_name} is not a valid hostname")
            return

        new_name = new_name.upper()
        name = name.upper()

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.warning(f"Device {name} not found in ldap, doing nothing.")
            return

        # Check if new_name is already used
        if self.lr.get(f'/devices/{new_name}'):
            logging.warning(f"{new_name} is already used, please use another hostname.")
            return

        # Update attributes

        data = {
            "displayName": f"Computer {new_name}",
            "dNSHostName": details["dNSHostName"].replace(name, new_name),
            "sAMAccountName": details["sAMAccountName"].replace(name, new_name),
            "servicePrincipalName": [spn.replace(name, new_name) for spn in details["servicePrincipalName"]],
            "sophomorixDnsNodename": new_name.lower()
        }

        self.setattr(name, data=data)

        self.lw._rename(details['dn'], new_name)

    def move(self, name, new_room):
        """
        Move a device to another room, e.g. to another OU

        :param name: name of the device to move
        :type name: basestring
        :param new_room: New OU for the device
        :type new_room: basestring
        """


        if not Validator.check_host_name(new_room):
            logging.error(f"{new_room} is not a valid room name")
            return

        if not self.lr.getval(f"/rooms/{new_room}", 'cn'):
            logging.error(f"Can not move to {new_room}, this group does not exist in LDAP.")
            return

        name = name.upper()

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.warning(f"Device {name} not found in ldap, doing nothing.")
            return

        # Build new parent OU
        dn_splitted = details['dn'].split(',')
        old_room = dn_splitted[1].split('=')[1]
        ou_prefix = ','.join(dn_splitted[:2])

        new_ou = details['dn'].replace(f"{ou_prefix},", f"OU={new_room},")
        new_dn = f"CN={name},{new_ou}"

        # Move to new OU
        self.lw._move(details['dn'], new_ou)

        # Update attributes

        data = {
            "sophomorixAdminClass": new_room,
            "sophomorixComputerRoom": new_room,
        }
        self.setattr(name, data=data)

        # Update membership

        old_group = details['dn'].replace(f"CN={name},", f"CN={old_room},")
        new_group = new_dn.replace(f"CN={name},", f"CN={new_room},")

        self.ow.remove_member(old_group, new_dn)
        self.ow.add_member(new_group, new_dn)


    def create_room(self, new_room, school='default-school', data={}):
        """
        Create a new room, e.g. another OU

        :param new_room: New OU to create
        :type new_room: basestring
        """


        if not Validator.check_host_name(new_room):
            logging.error(f"{new_room} is not a valid room name")
            return

        if new_room in self.lr.getval(f"/ou/rooms", 'name'):
            logging.error(f"Organizational unit {new_room} already exists in LDAP.")
            return

        if self.lr.getval(f"/rooms/{new_room}", 'cn'):
            logging.error(f"Group {new_room} already exists in LDAP.")
            return

        ## Create OU
        ou_dn = f"OU={new_room},OU=Devices,OU={school},{LDAP_CONTEXT}"
        self.lw._add_ou(ou_dn)

        ## Create group
        ldif = []
        group_dn = f"CN={new_room},{ou_dn}"
        valid_fields = {field.name:field.type() for field in fields(LMNRoom) if field.init}

        for attr,value in data.items():
            if attr in valid_fields:
                if isinstance(valid_fields[attr], list) and isinstance(value, list):
                    for val in value:
                        ldif.append((attr, [f"{val}".encode()]))
                else:
                    ldif.append((attr, [f"{value}".encode()]))
            else:
                logging.warning(f"Attribute {attr} not found in LMNRoom details")

        self.lw._add_group(group_dn, ldif)