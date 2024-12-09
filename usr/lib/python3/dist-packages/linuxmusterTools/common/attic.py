import os
import logging

from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from .convert import convert_sophomorix_time


def get_killdate(user, school='default-school'):
    """
    Get kill date of an user, if it exists.
    Actually only works with default-school on a single school instance.

    :param user:
    :type user:
    :param school:
    :type school:
    :return:
    :rtype:
    """


    if school != 'default-school':
        logging.warning("This functionality only works on default-school.")

    try:
        killlog = open("/var/log/sophomorix/userlog/user-kill.log", "r")
        for line in reversed(list(killlog)):
            if f'::{user}::' in line:
                killdate = convert_sophomorix_time(line.split('::')[2])
                killlog.close()
                return killdate
    except Exception as e:
        killlog.close()
        logging.warning(str(e))


def check_attic_dir(school='default-school'):
    """
    Checks the attic dir if some directories can be definitively be deleted.
    Actually only works with default-school on a single school instance.

    :param school:
    :type school:
    :return:
    :rtype:
    """


    if school != 'default-school':
        logging.warning("This functionality only works on default-school.")

    attic_dir = "/srv/samba/schools/default-school/students/attic"

    result = {}
    for user in os.listdir(attic_dir):
        if not lr.get(f'/users/{user}'):
            killdate = get_killdate(user)
            result[user] = killdate

    return result