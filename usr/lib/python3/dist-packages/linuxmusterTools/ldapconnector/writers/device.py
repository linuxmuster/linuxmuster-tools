import logging
from dataclasses import fields

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from ..models import LMNDeviceModel, LMNRoomModel, LMNGroupModel
from linuxmusterTools.common import Validator
from linuxmusterTools.lmnconfig import LDAP_CONTEXT, SAMBA_REALM
from linuxmusterTools.common.checks import NameChecker, check_tmp_dir
from linuxmusterTools.devices import Devices


name_checker = NameChecker()
logger = logging.getLogger(__name__)
devices_list = Devices()

class LMNRoom:

    def __init__(self, cn, school='default-school'):

        if not name_checker.check_room_name(cn):
            raise Exception(f"{cn} is not a valid CN")

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        self.model = LMNRoomModel
        self.data = {}
        self.new = False
        self.school = school
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/rooms/{self.cn}', school=self.school)

        if not self.data:
            logger.info(f"The room {self.cn} was not found in ldap.")
            self.new = True
            self.data =  {field.name:field.type() for field in fields(self.model) if field.init}
            self.data['cn'] = self.cn

    def setattr(self, **kwargs):
        """
        Set some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """

        if not self.new:
            self.lw._setattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')


    def delattr(self, **kwargs):
        """
        Delete some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """

        if not self.new:
            self.lw._delattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')


    def getattr(self, attr):
        """
        Get a specific attribute of the object.
        """

        return self.data.get(attr, None)


class LMNDevice:

    def __init__(self, cn, school='default-school', printer=False):
        """
        This class can handle any device registered in Ldap. Not all devices in
        the devices.csv are registered in Ldap (server, router, etc ... are not).
        """


        if not name_checker.check_host_name(cn):
            raise Exception(f"{cn} is not a valid CN")

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        if printer:
            self.model = LMNGroupModel
        else:
            self.model = LMNDeviceModel
        self.data = {}
        self.new = False
        self.pxe = False
        self.school = school
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/devices/{self.cn}', school=self.school)

        devices_list.switch(self.school)

        csvdetails = devices_list.get_host(self.cn)
        if csvdetails is not None:
            self.data['csvdetails'] = csvdetails
            self.pxe = csvdetails.get('pxeFlag', None) == '1'

        if not self.data:
            if csvdetails is not None:
                # TODO Check if not imported or regular (router)
                pass
            else:
                logger.info(f"The device {self.cn} was not found in ldap.")
                self.new = True
                self.data =  {field.name:field.type() for field in fields(self.model) if field.init}
                self.data['cn'] = self.cn

    def setattr(self, **kwargs):
        """
        Set some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """


        if not self.new:
            self.lw._setattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def delattr(self, **kwargs):
        """
        Delete some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """

        if not self.new:
            self.lw._delattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def getattr(self, attr):
        """
        Get a specific attribute of the object.
        """

        return self.data.get(attr, None)

    def rename(self, new_cn):
        """
        Rename a device inside a room.
        """


        if not name_checker.check_host_name(new_cn):
            logger.error(f"{new_cn} is not a valid hostname")
            return

        new_cn = new_cn.upper()
        cn = self.data['cn'].upper()

        # Check if new_name is already used
        if self.lr.get(f'/devices/{new_cn}'):
            logger.warning(f"{new_cn} is already used, please use another hostname.")
            return

        # Update attributes

        data = {
            "displayName": f"Computer {new_cn}",
            "dNSHostName": f"{new_cn}.{SAMBA_REALM}",
            "sAMAccountName": f"{new_cn}$",
            "servicePrincipalName": [
                f'HOST/{new_cn}',
                f'HOST/{new_cn}.{SAMBA_REALM}',
                f'RestrictedKrbHost/{new_cn}',
                f'RestrictedKrbHost/{new_cn}.{SAMBA_REALM}'
            ],
            "sophomorixDnsNodename": new_cn.lower(),
        }

        self.setattr(data=data)

        self.lw._rename(self.data['dn'], new_cn)
    #
    # def move(self, name, new_room):
    #     """
    #     Move a device to another room, e.g. to another OU
    #
    #     :param name: name of the device to move
    #     :type name: basestring
    #     :param new_room: New OU for the device
    #     :type new_room: basestring
    #     """
    #
    #
    #     if not Validator.check_host_name(new_room):
    #         logger.error(f"{new_room} is not a valid room name")
    #         return
    #
    #     if not self.lr.getval(f"/rooms/{new_room}", 'cn'):
    #         logger.error(f"Can not move to {new_room}, this group does not exist in LDAP.")
    #         return
    #
    #     name = name.upper()
    #
    #     details = self.lr.get(f'/devices/{name}')
    #
    #     if not details:
    #         logger.warning(f"Device {name} not found in ldap, doing nothing.")
    #         return
    #
    #     # Build new parent OU
    #     dn_splitted = details['dn'].split(',')
    #     old_room = dn_splitted[1].split('=')[1]
    #     ou_prefix = ','.join(dn_splitted[:2])
    #
    #     new_ou = details['dn'].replace(f"{ou_prefix},", f"OU={new_room},")
    #     new_dn = f"CN={name},{new_ou}"
    #
    #     # Move to new OU
    #     self.lw._move(details['dn'], new_ou)
    #
    #     # Update attributes
    #
    #     data = {
    #         "sophomorixAdminClass": new_room,
    #         "sophomorixComputerRoom": new_room,
    #     }
    #     self.setattr(name, data=data)
    #
    #     # Update membership
    #
    #     old_group = details['dn'].replace(f"CN={name},", f"CN={old_room},")
    #     new_group = new_dn.replace(f"CN={name},", f"CN={new_room},")
    #
    #     self.ow.remove_member(old_group, new_dn)
    #     self.ow.add_member(new_group, new_dn)
    #
    # def delete_room(self, room, school='default-school'):
    #     """
    #     Delete the OU and his group associated to a room, if this does not contain any device.
    #
    #     :param room: Name of the room to dele
    #     :type room: basestring
    #     :param school: Concerned school
    #     :type school: basestring
    #     """
    #
    #
    #     if room not in self.lr.getval(f"/ou/rooms", 'name'):
    #         logger.error(f"Organizational unit {room} doesn't exist in LDAP.")
    #         return
    #
    #     group = self.lr.get(f'/rooms/{room}')
    #     if group and len(group['member']) > 0:
    #         logger.error(f"Room {room} still contain some devices, can not delete it.")
    #         return
    #
    #     ou_dn = f"OU={room},OU=Devices,OU={school},{LDAP_CONTEXT}"
    #     self.lw._del(ou_dn)
    #
    # def create_room(self, new_room, school='default-school', data={}):
    #     """
    #     Create a new room, e.g. another OU
    #
    #     :param new_room: New OU to create
    #     :type new_room: basestring
    #     :param school: Concerned school
    #     :type school: basestring
    #     """
    #
    #
    #     if not Validator.check_host_name(new_room):
    #         logger.error(f"{new_room} is not a valid room name")
    #         return
    #
    #     if new_room in self.lr.getval(f"/ou/rooms", 'name'):
    #         logger.error(f"Organizational unit {new_room} already exists in LDAP.")
    #         return
    #
    #     if self.lr.getval(f"/rooms/{new_room}", 'cn'):
    #         logger.error(f"Group {new_room} already exists in LDAP.")
    #         return
    #
    #     ## Create OU
    #     ou_dn = f"OU={new_room},OU=Devices,OU={school},{LDAP_CONTEXT}"
    #     self.lw._add_ou(ou_dn)
    #
    #     ## Create group
    #     ldif = []
    #     group_dn = f"CN={new_room},{ou_dn}"
    #     valid_fields = {field.name:field.type() for field in fields(LMNRoomModel) if field.init}
    #
    #     for attr,value in data.items():
    #         if attr in valid_fields:
    #             if isinstance(valid_fields[attr], list) and isinstance(value, list):
    #                 for val in value:
    #                     ldif.append((attr, [f"{val}".encode()]))
    #             else:
    #                 ldif.append((attr, [f"{value}".encode()]))
    #         else:
    #             logger.warning(f"Attribute {attr} not found in LMNRoom details")
    #
    #     self.lw._add_group(group_dn, ldif)

class LMNPrinter(LMNDevice):

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school = school, printer=True)
        if self.data.get('sophomorixType', None) != 'printer':
            raise Exception(f'{cn} is not a valid printer.')

    def load_data(self):
        self.data = self.lr.get(f'/printers/{self.cn}', school=self.school)

        devices_list.switch(self.school)

        csvdetails = devices_list.get_host(self.cn)
        if csvdetails is not None:
            self.data['csvdetails'] = csvdetails
            self.pxe = csvdetails.get('pxeFlag', None) == '1'

        if not self.data:
            if csvdetails is not None:
                # TODO Check if not imported or regular (router)
                pass
            else:
                logger.info(f"The device {self.cn} was not found in ldap.")
                self.new = True
                self.data =  {field.name:field.type() for field in fields(self.model) if field.init}
                self.data['cn'] = self.cn

    def remove_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The object {user} was not found in ldap.")

        try:
            members = self.data['member']
            if user_dn in members:
                members.remove(user_dn)
            else:
                logging.info(f"{user} is not a member of schoolclass {self.cn}")
                return
            if members:
                self.lw._setattr(self, data={'member': members})
            else:
                self.lw._delattr(self, data={'member': None})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove member {user_dn} from {self.cn}: {str(e)}")

    def remove_all_members(self):
        try:
            self.lw._delattr(self, data={'member': None})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove all members from {self.cn}: {str(e)}")

    def add_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The user {user} was not found in ldap.")

        try:
            members = self.data['member']
            members.append(user_dn)
            self.lw._setattr(self, data={'member': members})
            self.load_data()
        except Exception as e:
            logger.warning(f"Could not append member {user_dn} to {self.cn}: {str(e)}")

    def add_members(self, userlist):
        """
        Shortcut to add all members from a given list

        :param userlist: List of valid cn
        """


        for user in userlist:
            self.add_member(user)
