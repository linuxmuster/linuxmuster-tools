class SchoolError(Exception):
    """
    Raised when an operation is given an invalid or unresolvable school scope,
    e.g. 'global' where a single, concrete school is required.
    """


class LdapNotProvisionedError(Exception):
    """
    Raised when LDAP/Samba credentials are requested before linuxmuster-setup
    has provisioned the domain (e.g. fresh install, setup wizard not completed yet).
    """
