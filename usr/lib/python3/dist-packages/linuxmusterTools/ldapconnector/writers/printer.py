import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router


logger = logging.getLogger(__name__)

class LMNPrinterWriter:

    def __init__(self):
        self.lw = LdapWriter()
        self.lr = router

    def setattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/printers/{name}')

        if not details:
            logger.info(f"The printer {name} was not found in ldap.")
            raise Exception(f"The printer {name} was not found in ldap.")

        self.lw._setattr(details, **kwargs)

    def delattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/printers/{name}')

        if not details:
            logger.info(f"The printer {name} was not found in ldap.")
            raise Exception(f"The printer {name} was not found in ldap.")

        self.lw._delattr(details, **kwargs)
