import os
import logging
from datetime import datetime

from linuxmusterTools.ldapconnector import LMNLdapReader as lr


def convert_sophomorix_time(t):
    """
    Convert sophomorix datetime to readable info.
    May not be the right place here.

    :param t: Sophomorix date like 20081030125303.0Z
    :type t: basestring
    :return: Human-readable date like 30 Oct 2008 12:53:30
    :rtype:
    """


    try:
        return  datetime.strptime(t, '%Y%m%d%H%M%S.%fZ').strftime("%d %b %Y %H:%M:%S")
    except Exception:
        return t

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