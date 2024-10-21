import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router

class LMNSchoolclassWriter:

    def __init__(self):
        self.lw = LdapWriter()
        self.lr = router

    def setattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/schoolclasses/{name}')

        if not details:
            logging.info(f"The schoolclass {name} was not found in ldap.")
            raise Exception(f"The schoolclass {name} was not found in ldap.")

        self.lw._setattr(details, **kwargs)

    def delattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/schoolclasses/{name}')

        if not details:
            logging.info(f"The schoolclass {name} was not found in ldap.")
            raise Exception(f"The schoolclass {name} was not found in ldap.")

        self.lw._delattr(details, **kwargs)
