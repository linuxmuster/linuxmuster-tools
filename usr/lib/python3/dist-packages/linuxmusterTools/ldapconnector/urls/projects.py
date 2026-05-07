import ldap.filter
import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.single(r'/projects/(?P<project>[a-zA-Z0-9_\-äëïöüÄËÏÖÜßéàèùçÀÉÈÇÙâêîôûÂÊÛÔÎ]*)', models.LMNProjectModel)
def get_project(project):
    """
    Get all details from a specific project.
    Return a LMNProjectModel data object
    """

    project = ldap.filter.escape_filter_chars(project)
    return f"""(&(cn={project})(objectClass=group)(sophomorixType=project))"""

@router.collection(r'/projects', models.LMNProjectModel)
def get_all_projects():
    """
    Get all projects details.
    Return a list of LMNProjectModel data objects.
    """

    return """(&(objectClass=group)(sophomorixType=project))"""
