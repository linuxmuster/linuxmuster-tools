import ldap.filter
import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.single(r'/staff/(?P<staffgroup>[\w\-_ ]*)', models.LMNSchoolClassModel)
def get_staffgroup(staffgroup):
    """
    Get all details from a specific staffgroup.
    Return a LMNSchoolClassModel data object
    """

    staffgroup = ldap.filter.escape_filter_chars(staffgroup)
    return f"""(&(cn={staffgroup})(objectClass=group)(sophomorixType=staffclass))"""

@router.collection(r'/staff/(?P<staffgroup>[a-z0-9\-_]*)/members', models.LMNUserModel)
def get_all_members_from_staffgroup(staffgroup):
    """
    Get all members details from a specific staffgroup.
    Return a list of LMNUserModel data objects.
    """

    staffgroup = ldap.filter.escape_filter_chars(staffgroup)
    return f"""(&
                                (objectClass=user)
                                (sophomorixAdminClass={staffgroup})
                                (sophomorixRole=staff)
                            )"""

@router.collection(r'/staff', models.LMNSchoolClassModel)
def get_all_staff():
    """
    Get all staff details.
    Return a list of LMNSchoolClassModel data objects.
    """

    return """(&(objectClass=group)(sophomorixType=staffclass))"""

@router.collection(r'/staff/search/(?P<query>\w*)', models.LMNSchoolClassModel)
def get_results_search_staff(query):
    """
    Get all details from a search about staff.
    Return a list of LMNSchoolClassModel data objects.
    """

    query = ldap.filter.escape_filter_chars(query)
    return f"""(&(objectClass=group)(sophomorixType=staffclass)(cn=*{query}*))"""

@router.collection(r'/empty_staff', models.LMNSchoolClassModel)
def get_results_search_empty_staff():
    """
    Get all details from empty staff.
    Return a list of LMNSchoolClassModel data objects.
    """

    return f"""(&(objectClass=group)(sophomorixType=staffclass)(!(sophomorixMembers=*)))"""
