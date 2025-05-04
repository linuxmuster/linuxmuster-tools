import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router

@router.collection(r'/schools', models.LMNSchoolModel, subdn='OU=SCHOOLS,', level="single")
def get_all_schools():
    """
    Get all schools.
    Return a LMNSchoolModel data object
    """

    return f"""(&(objectClass=organizationalUnit))"""


@router.single(r'/schools/(?P<school>[a-zA-Z0-9_\-äëïöüÄËÏÖÜßéàèùçÀÉÈÇÙâêîôûÂÊÛÔÎ]*)', models.LMNSchoolModel, subdn='OU=SCHOOLS,', level="single")
def get_specific_school(school):
    """
    Get a specific school.
    Return a LMNSchoolModel data object
    """

    return f"""(&(objectClass=organizationalUnit)(name={school}))"""