import os
import logging
import datetime

from linuxmusterTools.lmnconfig import SchoolConfig
from linuxmusterTools.ldapconnector import LMNLdapReader as lr
from linuxmusterTools.smbclient import LMNSMBClient
from .convert import convert_sophomorix_time


logger = logging.getLogger(__name__)

def get_killdate(user):
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


    try:
        # Same log path for all schools
        with open("/var/log/sophomorix/userlog/user-kill.log", "r") as killlog:
            for line in reversed(list(killlog)):
                if f'::{user}::' in line:
                    details = line.split('::')
                    killdate = convert_sophomorix_time(details[2])
                    school = details[3]
                    return killdate, school
    except Exception as e:
        logger.warning(str(e))
        return None, None


    return None, None

def get_attic_status(user):
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


    details = lr.get(f'/users/{user}')

    result = {'status': 'No information found.', 'start':'', 'end':'', 'school': 'Unknown'}

    if not details:
        killdate, school = get_killdate(user)
        if killdate is not None:
            result['school'] = school
            result['status'] = "killed"
            result['start'] = killdate
            result['end'] = killdate
            return result
        else:
            return result

    if details['sophomorixAdminClass'] != 'attic':
        logger.warning(f"User {user} is not an attic user, exiting.")
        result['status'] = "Activated"
        return result

    status = details['sophomorixStatus']
    admin_file = details['sophomorixAdminFile']
    sophomorix_config = SchoolConfig(school=details['school']).config
    role_config = sophomorix_config.get(f'userfile.{admin_file}', {})

    result['school'] = details['school']

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


    logger.warning("This functionality is still experimental")

    if not school:
        # If school is None, checking all schools
        to_check = lr.getval('/schools', 'ou')
    else:
        to_check = [school]

    client = LMNSMBClient()
    result = {}

    for s in to_check:
        client.switch(s)
        attic_dirs = [entry['name'] for entry in client.list('students/attic')]

        for user in attic_dirs:

            if user not in ['.', '..']:
                result[user] = get_attic_status(user)

    return result

