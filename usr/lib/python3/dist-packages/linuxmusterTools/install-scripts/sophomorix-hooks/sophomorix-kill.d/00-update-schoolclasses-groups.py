#! /usr/bin/env python3

# This script is part of the sophomorix project and intended to delete
# obsolete CN of parents in students OU
# DO NOT EDIT OR REMOVE IT !

import sys
from linuxmusterTools.common import *
from linuxmusterTools.ldapconnector import LMNUser, LMNSchoolclass


# sophomorix also passes the school as second argument, but it is not
# used: the sophomorix logs are global files and carry the school of
# every entry, so one copy of this hook handles all the schools.
epoch = sys.argv[1]

if epoch is None:
    updates = parse_kill_log(today=True)
    timestamps = list(updates.keys())
    timestamps.sort()
    epoch = timestamps[-1]
    entries = updates[epoch]
else:
    entries = parse_kill_log(epoch=epoch)

# Nothing to do at this point.