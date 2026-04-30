from .render import LatexRenderer
from .templates import *


def print_schoolclass_list(schoolclass, caller, school='default_school', template="schoolclass-DE-32-template.tex"):
    """
    Print a list of students from a specific schoolclass.

    :param caller: the user calling the process, for generating the filename
    :return: PDF path
    """

    templates = LatexTemplates().templates

    if template not in templates:
        raise Exception(f"Can not find the template {template}!")

    template_obj = templates[template]

    data = []
    students = lr.getval(f'/schoolclasses/{schoolclass}', 'sophomorixMembers')

    if not students:
        raise Exception(f"Schoolclass {schoolclass} not found or empty!")

    for student in students:
        details = lr.get(f'/users/{student}', asdict=False)
        data.append({'lastname':details.sn, 'firstname':details.givenName})

    data_sorted = sorted(data, key=lambda item: item['lastname']+item['firstname'])

    l = LatexRenderer(template_obj, data_sorted, caller, vars={"school":school, "schoolclass":schoolclass})
    return l.compile()

def print_schoolclasses_list(schoolclasses, caller, school='default_school', template="datalist-DE-32-template.tex"):
    """
    Print a list of students from multiple schoolclasses.

    :param schoolclasses: list of schoolclasses
    :param caller: the user calling the process, for generating the filename
    :return: PDF path
    """

    pass
