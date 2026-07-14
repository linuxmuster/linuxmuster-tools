from .render import LatexRenderer
from .templates import *
from ..lmnconfig import SchoolConfig, SAMBA_WORKGROUP


def print_passwords_list(schoolclass, caller, school='default-school', large=False, template="passwords-DE-1-template.tex"):
    """
    Print the password letters/cards of the students from a specific schoolclass.

    :param caller: the user calling the process, for generating the filename
    :param large: use the passwordslarge templates (bigger cards, 18 per page instead of 36)
    :return: PDF path
    """

    if large and template.startswith("passwords-"):
        template = template.replace("passwords-", "passwordslarge-", 1)

    templates = LatexTemplates().templates

    if template not in templates:
        raise Exception(f"Can not find the template {template}!")

    template_obj = templates[template]

    students = lr.getval(f'/schoolclasses/{schoolclass}', 'sophomorixMembers', school=school)

    if not students:
        raise Exception(f"Schoolclass {schoolclass} not found or empty!")

    data = []
    for student in students:
        details = lr.get(f'/users/{student}', as_dict=False, school=school)
        data.append({
            'lastname': details.sn,
            'firstname': details.givenName,
            'login': details.sAMAccountName,
            'password': details.sophomorixFirstPassword,
            'schoolclass': schoolclass,
        })

    data_sorted = sorted(data, key=lambda item: item['lastname']+item['firstname'])

    teachers = lr.getval(f'/schoolclasses/{schoolclass}', 'sophomorixAdmins', school=school) or []
    teachermembers = ", ".join(
        f"{teacher.givenName} {teacher.sn}"
        for teacher in (lr.get(f'/users/{login}', as_dict=False, school=school) for login in teachers)
    )

    sophomorix_config = SchoolConfig(school=school).config.get('school', {})

    vars = {
        "schoolclass": schoolclass,
        "school_longname": sophomorix_config.get('SCHOOL_LONGNAME', ''),
        "filename": f"{caller}-passwords-{schoolclass}",
        "admins_print": sophomorix_config.get('ADMINS_PRINT', ''),
        "domain": SAMBA_WORKGROUP,
        "teachermembers": teachermembers,
        "urlstart_print": sophomorix_config.get('URLSTART_PRINT', ''),
        "urlstart_comment_print": sophomorix_config.get('URLSTART_COMMENT_PRINT', ''),
        "urlschuko_print": sophomorix_config.get('URLSCHUKO_PRINT', ''),
        "urlschuko_comment_print": sophomorix_config.get('URLSCHUKO_COMMENT_PRINT', ''),
        "urlmail_print": sophomorix_config.get('URLMAIL_PRINT', ''),
        "urlmail_comment_print": sophomorix_config.get('URLMAIL_COMMENT_PRINT', ''),
        "urlmoodle_print": sophomorix_config.get('URLMOODLE_PRINT', ''),
        "urlmoodle_comment_print": sophomorix_config.get('URLMOODLE_COMMENT_PRINT', ''),
    }

    l = LatexRenderer(template_obj, data_sorted, caller, vars=vars)
    return l.compile()
