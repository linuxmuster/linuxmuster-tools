import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

import pytest
from unittest.mock import MagicMock

SEARCHDN = 'DC=linuxmuster,DC=lan'
USER_DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
GROUP_DN = 'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
PROJECT_DN = 'CN=p_robotics,OU=Projects,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_USER = {
    'cn': 'johndoe', 'displayName': 'John Doe', 'distinguishedName': USER_DN,
    'givenName': 'John', 'homeDirectory': '\\\\lmn\\students\\7a\\johndoe',
    'homeDrive': 'H:', 'mail': [], 'memberOf': [], 'name': 'johndoe',
    'objectClass': ['top', 'person', 'user'], 'preferredLanguage': '',
    'proxyAddresses': [], 'sAMAccountName': 'johndoe', 'sAMAccountType': '',
    'sn': 'Doe', 'sophomorixAdminClass': '7a', 'sophomorixAdminFile': 'students.csv',
    'sophomorixBirthdate': '', 'sophomorixCloudQuotaCalculated': '',
    'sophomorixComment': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [], 'sophomorixCustomMulti3': [],
    'sophomorixCustomMulti4': [], 'sophomorixCustomMulti5': [],
    'sophomorixDeactivationDate': '', 'sophomorixExamMode': [],
    'sophomorixExitAdminClass': '', 'sophomorixFirstnameASCII': 'John',
    'sophomorixFirstnameInitial': 'J', 'sophomorixFirstPassword': '',
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '', 'sophomorixIntrinsic3': '',
    'sophomorixIntrinsic4': '', 'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [], 'sophomorixIntrinsicMulti3': [],
    'sophomorixIntrinsicMulti4': [], 'sophomorixIntrinsicMulti5': [],
    'sophomorixMailQuotaCalculated': '', 'sophomorixMailQuota': [], 'sophomorixQuota': [],
    'sophomorixRole': 'student', 'sophomorixSchoolname': 'default-school',
    'sophomorixSchoolPrefix': '---', 'sophomorixSessions': [],
    'sophomorixStatus': 'U', 'sophomorixSurnameASCII': 'Doe',
    'sophomorixSurnameInitial': 'D', 'sophomorixTolerationDate': '',
    'sophomorixUnid': '', 'sophomorixUserToken': '',
    'sophomorixWebuiDashboard': [], 'sophomorixWebuiPermissionsCalculated': [],
    'thumbnailPhoto': '', 'unixHomeDirectory': '/home/default-school/students/7a/johndoe',
    'userAccountControl': 66048, 'whenChanged': '',
    'dn': USER_DN, 'children': [], 'customFields': {}, 'examMode': False,
    'examTeacher': '', 'examBaseCn': '', 'internet': False, 'intranet': False,
    'isAdmin': False, 'lmnsessions': [], 'parents': [], 'permissions': {},
    'printers': [], 'printing': False, 'projects': [], 'schoolclasses': ['7a'],
    'school': 'default-school', 'webfilter': False, 'wifi': False,
}

SAMPLE_GROUP = {
    'cn': '7a', 'description': '', 'displayName': '7a', 'distinguishedName': GROUP_DN,
    'mail': [], 'member': [USER_DN], 'memberOf': [], 'name': '7a', 'objectClass': [],
    'proxyAddresses': [], 'sAMAccountName': '7a', 'sAMAccountType': '',
    'sophomorixAdminClass': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [], 'sophomorixCustomMulti3': [],
    'sophomorixCustomMulti4': [], 'sophomorixCustomMulti5': [],
    'sophomorixHidden': False, 'sophomorixJoinable': False,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '', 'sophomorixIntrinsic3': '',
    'sophomorixIntrinsic4': '', 'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [], 'sophomorixIntrinsicMulti3': [],
    'sophomorixIntrinsicMulti4': [], 'sophomorixIntrinsicMulti5': [],
    'sophomorixMailAlias': False, 'sophomorixMailList': False,
    'sophomorixMembers': ['johndoe'], 'sophomorixRole': '',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixStatus': '', 'sophomorixType': 'adminclass',
    'dn': GROUP_DN, 'all_members': [], 'membersCount': -1,
}

SAMPLE_PROJECT = {
    'cn': 'robotics', 'description': 'robotics', 'displayName': 'robotics',
    'distinguishedName': PROJECT_DN, 'mail': [], 'member': [], 'name': 'robotics',
    'objectClass': [], 'proxyAddresses': [], 'sAMAccountName': 'robotics', 'sAMAccountType': '',
    'sophomorixAddMailQuota': [], 'sophomorixAddQuota': [], 'sophomorixAdminGroups': [],
    'sophomorixAdmins': [], 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [], 'sophomorixCustomMulti3': [],
    'sophomorixCustomMulti4': [], 'sophomorixCustomMulti5': [],
    'sophomorixHidden': False,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '', 'sophomorixIntrinsic3': '',
    'sophomorixIntrinsic4': '', 'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [], 'sophomorixIntrinsicMulti3': [],
    'sophomorixIntrinsicMulti4': [], 'sophomorixIntrinsicMulti5': [],
    'sophomorixJoinable': False, 'sophomorixMailAlias': False, 'sophomorixMailList': False,
    'sophomorixMailQuota': [], 'sophomorixMaxMembers': 0, 'sophomorixMemberGroups': [],
    'sophomorixMembers': ['johndoe'], 'sophomorixQuota': [],
    'sophomorixSchoolname': 'default-school', 'sophomorixStatus': '', 'sophomorixType': 'project',
    'dn': PROJECT_DN, 'all_members': [], 'all_admins': [], 'membersCount': -1, 'adminsCount': -1,
}


@pytest.fixture(autouse=True)
def reset_ldap_pool():
    import linuxmusterTools.ldapconnector.connector as conn_module
    conn_module.local_thread.conn = None
    yield
    conn_module.local_thread.conn = None


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.search_s.return_value = []
    return conn


@pytest.fixture
def mock_connect(mock_conn, monkeypatch):
    from linuxmusterTools.ldapconnector.connector import LdapConnector
    monkeypatch.setattr(LdapConnector, '_connect', lambda self: (mock_conn, SEARCHDN))
    return mock_conn
