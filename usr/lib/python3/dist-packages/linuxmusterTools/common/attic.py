import os
import logging
import datetime

from linuxmusterTools.lmnconfig import SophomorixConfig
from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from .convert import convert_sophomorix_time


def get_killdate(user, school='default-school'):
    """
    Get kill date of an user, if it exists.
    Actually only works with default-school on a single school instance.

    :param user: user login
    :type user: basestring
    :param school: school of the user
    :type school: basestring
    :return: Date when the account was killed, if it was the case
    :rtype: basestring
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
        return None
    return None

def get_attic_status(user, school='default-school'):
    """
    Get the actual status of an user in attic.
    Actually only works with default-school on a single school instance.

    :param user: user login
    :type user: basestring
    :param school: school of the user
    :type school: basestring
    :return: toleration, deactivation or killable status and date
    :rtype:
    """


    if school != 'default-school':
        logging.warning("This functionality only works on default-school.")

    details = lr.get(f'/users/{user}')

    result = {'status': 'No information found.', 'start':'', 'end':''}

    if not details:
        killdate = get_killdate(user, school=school)
        if killdate is not None:
            result['status'] = "killed"
            result['start'] = killdate
            result['end'] = killdate
            return result
        else:
            return result

    if details['sophomorixAdminClass'] != 'attic':
        logging.warning(f"User {user} is not an attic user, exiting.")
        result['status'] = "Activated"
        return result

    status = details['sophomorixStatus']
    admin_file = details['sophomorixAdminFile']
    sophomorix_config = SophomorixConfig().config
    role_config = sophomorix_config.get(f'userfile.{admin_file}', {})

    if status == "M" or status == "T":
        # Status Managed or Tolerates
        start = datetime.datetime.strptime(details['sophomorixTolerationDate'], '%Y%m%d%H%M%S.%fZ')
        result['start'] = start.strftime("%d %b %Y %H:%M:%S")
        result['status'] = "tolerated"
        result['end'] = (start + datetime.timedelta(days=int(role_config['TOLERATION_TIME']))).strftime("%d %b %Y %H:%M:%S")
    elif status == "D" or status == "L":
        # Status Deactivated or Locked
        start = datetime.datetime.strptime(details['sophomorixDeactivationDate'], '%Y%m%d%H%M%S.%fZ')
        result['start'] = start.strftime("%d %b %Y %H:%M:%S")
        result['status'] = "deactivated"
        result['end'] = (start + datetime.timedelta(days=int(role_config['DEACTIVATION_TIME']))).strftime("%d %b %Y %H:%M:%S")
    elif status == "R" or status == "K":
        # Status Removable or Killable
        # Same start and end time
        start = datetime.datetime.strptime(details['sophomorixDeactivationDate'], '%Y%m%d%H%M%S.%fZ')
        result['start'] = (start + datetime.timedelta(days=int(role_config['DEACTIVATION_TIME']))).strftime("%d %b %Y %H:%M:%S")
        result['status'] = "killable"
        result['end'] = (start + datetime.timedelta(days=int(role_config['DEACTIVATION_TIME']))).strftime("%d %b %Y %H:%M:%S")

    return result

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
        result[user] = get_attic_status(user, school=school)
        # if not lr.get(f'/users/{user}'):
        #     killdate = get_killdate(user)
        #     result[user] = killdate

    return result

