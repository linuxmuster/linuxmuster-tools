from ..urls.ldaprouter import router as lr


def valid_schools():
    """
    List the schools actually provisioned in ldap.

    Note that 'global' is not a school but a routing marker, used to tell that
    a global-administrator is not scoped to a single school, so it is never
    part of this list.

    :return: List of school names (the ou of each school)
    :rtype: list
    """


    return lr.getval('/schools', 'ou')

def is_valid_school(school):
    """
    Check if the given school is provisioned in ldap.

    :param school: school name to check
    :type school: string
    :return: True if the school exists
    :rtype: bool
    """


    return school in valid_schools()
