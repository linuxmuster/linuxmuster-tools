import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.collection(r'/schools', models.LMNSchool, subdn='OU=SCHOOLS,', level="single")
def get_all_schools():
    """
    Get all schools.
    Return a LMNSchool data object
    """

    return f"""(&(objectClass=organizationalUnit))"""