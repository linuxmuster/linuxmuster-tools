import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.single(r'/schoolclasses/(?P<schoolclass>[\w\-_ ]*)', models.LMNSchoolClass)
def get_schoolclass(schoolclass):
    """
    Get all details from a specific schoolclass.
    Return a LMNSchoolClass data object
    """

    return f"""(&(cn={schoolclass})(objectClass=group)(sophomorixType=adminclass))"""

@router.collection(r'/schoolclasses/(?P<schoolclass>[a-z0-9\-_]*)/students', models.LMNUser)
def get_all_students_from_schoolclass(schoolclass):
    """
    Get all students details from a specific schoolclass.
    Return a list of LMNUser data objects.
    """

    return f"""(&
                                (objectClass=user)
                                (sophomorixAdminClass={schoolclass})
                                (sophomorixRole=student)
                            )"""

@router.collection(r'/schoolclasses', models.LMNSchoolClass)
def get_all_schoolclasses():
    """
    Get all schoolclasses details.
    Return a list of LMNSchoolClass data objects.
    """

    return """(&(objectClass=group)(sophomorixType=adminclass))"""

@router.collection(r'/schoolclasses/search/(?P<query>\w*)', models.LMNSchoolClass)
def get_results_search_schoolclasses(query):
    """
    Get all details from a search about schoolclasses.
    Return a list of LMNSchoolClass data objects.
    """

    return f"""(&(objectClass=group)(sophomorixType=adminclass)(cn=*{query}*))"""
