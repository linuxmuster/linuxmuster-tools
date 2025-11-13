from ..ldapconnector import LMNLdapReader as lr
from .render import LatexRenderer

def print_schoolclass_list(schoolclass, caller, school='default_school', template="schoolclass-DE-32-template.tex"):
    """
    Print a list of students from a specific schoolclass.

    :param caller: the user calling the process, for generating the filename
    :return: PDF path
    """


    # use displayname if defined instead of school cn ?
    # choice for templates !

    data = []
    students = lr.getval(f'/schoolclasses/{schoolclass}', 'sophomorixMembers')

    if not students:
        raise Exception(f"Schoolclass {schoolclass} not found or empty!")

    for student in students:
        details = lr.get(f'/users/{student}', dict=False)
        data.append({'lastname':details.sn, 'firstname':details.givenName})

    data_sorted = sorted(data, key=lambda item: item['lastname']+item['firstname'])

    l = LatexRenderer(template, "schoolclass", data_sorted, caller, vars={"school":school, "schoolclass":schoolclass})
    return l.compile()

def print_schoolclasses_list(schoolclasses, caller, school='default_school', template="datalist-DE-32-template.tex"):
    """
    Print a list of students from multiple schoolclasses.

    :param schoolclasses: list of schoolclasses
    :param caller: the user calling the process, for generating the filename
    :return: PDF path
    """

    pass
