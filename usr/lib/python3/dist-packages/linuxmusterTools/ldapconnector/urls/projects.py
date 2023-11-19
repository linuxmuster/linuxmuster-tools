import linuxmusterTools.ldapconnector.models as models
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


@router.single(r'/projects/(?P<project>[a-zA-Z0-9_\-]*)', models.LMNProject)
def get_project(project):
    """
    Get all details from a specific project.
    Return a LMNProject data object
    """

    return f"""(&(cn={project})(objectClass=group)(sophomorixType=project))"""

@router.collection(r'/projects', models.LMNProject)
def get_all_projects():
    """
    Get all projects details.
    Return a list of LMNProject data objects.
    """

    return """(&(objectClass=group)(sophomorixType=project))"""
