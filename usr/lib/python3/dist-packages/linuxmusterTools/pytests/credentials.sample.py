# Values of the test server, for the tests which need a real linuxmuster.net
# server. Copy this file to credentials.py (ignored by git) and fill it:
# private values like the domain, the SID or real logins must never be
# committed.
#
# The unit tests do not need it. A test which needs it loads it with:
#     credentials = pytest.importorskip('linuxmusterTools.pytests.credentials')
# so that it is skipped when credentials.py is missing.

# Samba domain
WORKGROUP = 'DOMAIN'             # workgroup in smb.conf
REALM = 'DOMAIN.LAN'             # realm in smb.conf
SERVER_IP = '10.0.0.1'

# Existing users, one per role
SCHOOL = 'default-school'
GLOBALADMIN = 'global-admin'
SCHOOLADMIN = 'SCHOOLADMINLOGIN'
TEACHER = 'TEACHERLOGIN'
STUDENT = 'STUDENTLOGIN'
STAFF = 'STAFFLOGIN'
PARENT = 'PARENTLOGIN'

# Existing objects, fill with actual values from your LDAP
SCHOOLCLASS = 'SCHOOLCLASSNAME'  # CN of an existing schoolclass
PROJECT = 'p_PROJECTNAME'        # CN of an existing project (with prefix)
PRINTER = 'PRINTERNAME'          # CN of an existing printer
DEVICE = 'DEVICENAME'            # hostname of an existing device
ROOM = 'ROOMNAME'                # room of DEVICE in devices.csv
