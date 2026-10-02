"""
Validation rules for the devices of a school.

The rules below are the naming rules of an Active Directory domain, taken
from the vendor documentation, not from the way sophomorix, the web ui or
this library happen to implement them today - those three disagree with
each other on several points:

https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/naming-conventions-for-computer-domain-site-ou

Every rule is a function validating one value and returning findings, so
that a caller writing a single attribute into the AD - LMNDevice.rename()
and the create() to come - checks exactly what a caller validating a whole
devices.csv checks. Add a rule here, never at a call site.

Validating a whole inventory is an object instead, InventoryValidator: it
carries what a single value does not - the computer roles read from
sophomorix.ini, the school and file a finding is stamped with, and the
values seen so far that uniqueness is checked against.
"""


import logging
from dataclasses import dataclass, field as dataclass_field, asdict

from ..common.checks import NameChecker
from ..lmnconfig import SophomorixIni


logger = logging.getLogger(__name__)

name_checker = NameChecker()

ERROR = 'error'
WARNING = 'warning'

# A machine account is a sAMAccountName, whose sixteenth byte is the service
# suffix - the trailing '$'. Fifteen characters are left for the name itself,
# and the domain does not count.
NETBIOS_NAME_MAX_LENGTH = 15

# Legal value of the ip field: the device gets its address from the dhcp
# server, so there is nothing to check and nothing to be unique.
DHCP = 'DHCP'

# The only named pxe value sophomorix knows (its %pxe hash), beside a digit.
PXE_NAMED_VALUES = ('ml',)

@dataclass
class Finding:
    """
    One problem found on one value.

    ``code`` is what a caller should branch on and what the web ui
    translates: the ``message`` is built here, in English, and can not be
    translated on the other side.
    """

    severity: str
    code: str
    message: str
    field: str = ''
    value: str = ''
    school: str = ''
    file: str = ''
    line: int = None
    subject: str = ''
    related: list = dataclass_field(default_factory=list)

    def as_dict(self):
        return asdict(self)


def prefixed_hostname(hostname, school='default-school'):
    """
    The name of a host as everything outside its own school writes it -
    sophomorix' own SCHOOLS.<school>.PREFIX. This is the name that lands in
    the AD, so this is the name the length limit applies to.

    :return: '<school>-<hostname>', or the hostname itself for default-school
    :rtype: string
    """


    if school and school != 'default-school':
        return f'{school}-{hostname}'
    return hostname


# Validation rules

def validate_room(room):
    """
    :param room: Value of the room field
    :type room: string
    :return: Findings, empty if the room name is valid
    :rtype: list
    """


    if not name_checker.check_room_name(room):
        return [Finding(
            ERROR, 'room.invalid', f"{room} is not a valid room name",
            field='room', value=room,
        )]
    return []


def validate_hostname(hostname, role='', school='default-school', roles=None):
    """
    Validate a host name against the AD naming rules.

    The length limit is checked on the prefixed name, since that is what
    sophomorix writes into the AD, and only for the roles that get a machine
    account - the limit comes from the sAMAccountName, so a role without one
    is not concerned.

    :param hostname: Value of the hostname field
    :type hostname: string
    :param role: sophomorixRole of the device, empty for the default role
    :type role: string
    :param school: School the device belongs to
    :type school: string
    :param roles: What sophomorix.ini says, read from the machine if not given
    :type roles: ComputerRoles
    :return: Findings, empty if the host name is valid
    :rtype: list
    """


    if not name_checker.check_host_name(hostname):
        # Every rule below reads the name character by character: reporting
        # them on a name already rejected would only repeat the same problem.
        return [Finding(
            ERROR, 'hostname.invalid', f"{hostname} is not a valid hostname",
            field='hostname', value=hostname,
        )]

    findings = []

    if hostname.isdigit():
        findings.append(Finding(
            ERROR, 'hostname.all_digits',
            f"{hostname} is not a valid hostname: a name can not be all digits",
            field='hostname', value=hostname,
        ))

    if not hostname[0].isalnum():
        findings.append(Finding(
            ERROR, 'hostname.leading_character',
            f"{hostname} is not a valid hostname: it must start with a letter or a digit",
            field='hostname', value=hostname,
        ))

    if hostname.endswith('-'):
        findings.append(Finding(
            ERROR, 'hostname.trailing_hyphen',
            f"{hostname} is not a valid hostname: it must not end with a hyphen",
            field='hostname', value=hostname,
        ))

    roles = roles or SophomorixIni().computer_roles

    # sophomorix substitutes COMPUTERROLE_DEFAULT for an empty role field.
    if (role or roles.default) in roles.accounts:
        full_name = prefixed_hostname(hostname, school)
        if len(full_name) > NETBIOS_NAME_MAX_LENGTH:
            findings.append(Finding(
                ERROR, 'hostname.too_long',
                f"{full_name} is longer than {NETBIOS_NAME_MAX_LENGTH} characters, "
                f"the maximum length of a machine account name",
                field='hostname', value=hostname,
            ))

    return findings


def validate_group(group):
    """
    :param group: Value of the group field, a LINBO group
    :type group: string
    :return: Findings, empty if the group name is valid
    :rtype: list
    """


    if not name_checker.check_linbo_conf_name(group):
        return [Finding(
            ERROR, 'group.invalid', f"{group} is not a valid Linbo group",
            field='group', value=group,
        )]
    return []


def validate_mac(mac):
    """
    :param mac: Value of the mac field, in any of the three accepted forms
    :type mac: string
    :return: Findings, empty if the address is valid
    :rtype: list
    """


    if not name_checker.normalize_mac(mac):
        return [Finding(
            ERROR, 'mac.invalid', f"{mac} is not a valid mac address",
            field='mac', value=mac,
        )]
    return []


def validate_ip(ip):
    """
    :param ip: Value of the ip field, or DHCP
    :type ip: string
    :return: Findings, empty if the address is valid
    :rtype: list
    """


    if ip == DHCP:
        return []

    if not name_checker.check_ip_name(ip):
        return [Finding(
            ERROR, 'ip.invalid', f"{ip} is not a valid ip address",
            field='ip', value=ip,
        )]
    return []


def validate_pxe_flag(pxe_flag):
    """
    Values of the pxeFlag field:

    - empty or 0: no pxe
    - 1: LINBO pxe, the only other value documented in devices.csv(5)
    - 2: formerly LINBO pxe + opsi management, still handled like 1 by
      linuxmuster-import-devices and linbo-remote
    - 3: formerly opsi pxe; since opsi was removed (linuxmuster-base7 #127),
      linuxmuster-import-devices still sets up pxe for it, but linbo-remote
      ignores it
    - ml: accepted by sophomorix-device (its %pxe hash), meaning undocumented

    Any other single digit is accepted too, as sophomorix-device does.

    :param pxe_flag: Value of the pxeFlag field
    :type pxe_flag: string
    :return: Findings, empty if the flag is valid
    :rtype: list
    """


    flag = (pxe_flag or '').strip()

    # An empty field means no pxe, as Devices._check_pxe_flag() already reads it.
    if not flag or flag in PXE_NAMED_VALUES or (len(flag) == 1 and flag.isdigit()):
        return []

    return [Finding(
        ERROR, 'pxe.invalid', f"{pxe_flag} is not a valid pxe flag",
        field='pxeFlag', value=pxe_flag,
    )]


def validate_role(role, roles=None):
    """
    :param role: Value of the sophomorixRole field, empty for the default role
    :type role: string
    :param roles: What sophomorix.ini says, read from the machine if not given
    :type roles: ComputerRoles
    :return: Findings, empty if the role is known to sophomorix.ini
    :rtype: list
    """


    # sophomorix substitutes COMPUTERROLE_DEFAULT for an empty field.
    if not role:
        return []

    if role not in (roles or SophomorixIni().computer_roles):
        return [Finding(
            ERROR, 'role.unknown', f"{role} is not a valid computer role",
            field='sophomorixRole', value=role,
        )]
    return []


def validate_device(device, school='default-school', file='', line=None, roles=None):
    """
    Apply every value rule to one device, as read from devices.csv.

    :param device: One row of devices.csv, enriched by Devices.load()
    :type device: dict
    :param roles: What sophomorix.ini says, read from the machine if not given
    :type roles: ComputerRoles
    :return: Findings on that device
    :rtype: list
    """


    hostname = device.get('hostname', '')
    role = device.get('sophomorixRole', '')
    roles = roles or SophomorixIni().computer_roles

    findings = []
    findings += validate_room(device.get('room', ''))
    findings += validate_hostname(hostname, role=role, school=school, roles=roles)
    findings += validate_group(device.get('group', ''))
    # The raw address, not the normalized one: normalize_mac() returns None
    # on a malformed address, and the report would name nothing.
    findings += validate_mac(device.get('macRaw', device.get('mac', '')))
    findings += validate_ip(device.get('ip', ''))
    findings += validate_pxe_flag(device.get('pxeFlag', ''))
    findings += validate_role(role, roles=roles)
    # officeKey and windowsKey are not checked: their only consumer, the
    # Windows reactivation of LINBO, was removed in linuxmuster-linbo7 7.4.0.

    # The value rules know nothing about where they were called from: stamp
    # the place on their findings here.
    for finding in findings:
        finding.school = school
        finding.file = file
        finding.line = device.get('csvLine', line)
        finding.subject = hostname

    return findings


# Inventory validation (duplicates, multischool ...)

class InventoryValidator:
    """
    Validate one or several device inventories at once, and report
    everything found instead of stopping at the first problem.

    Passing several inventories is what makes the cross school rules work:
    a host name or a mac address used in two schools can not be seen from
    one of them alone.
    """

    def __init__(self, inventories, roles=None):
        """
        :param inventories: Dicts of school, file and devices
        :type inventories: list
        :param roles: What sophomorix.ini says, read from the machine if not given
        :type roles: ComputerRoles
        """


        self.inventories = inventories
        self.roles = roles or SophomorixIni().computer_roles

    def validate(self):
        """
        Apply every rule, per value and across inventories.

        :return: valid, counts, findings as dicts and report as flat strings
        :rtype: dict
        """


        findings = []
        devices_count = 0

        for inventory in self.inventories:
            school = inventory.get('school', 'default-school')
            file = inventory.get('file', '')

            for device in inventory.get('devices', []):
                devices_count += 1
                findings += validate_device(
                    device, school=school, file=file, roles=self.roles
                )

        findings += self._check_uniqueness()

        errors = [f for f in findings if f.severity == ERROR]
        warnings = [f for f in findings if f.severity == WARNING]

        return {
            'valid': not errors,
            'counts': {
                'schools': len(self.inventories),
                'devices': devices_count,
                'errors': len(errors),
                'warnings': len(warnings),
            },
            'findings': [f.as_dict() for f in findings],
            # A flat list of strings, the form Subnets.check_conf() already
            # exposes, for a caller that only prints what it gets.
            'report': [self._text(f) for f in findings],
        }

    def _check_uniqueness(self):
        """
        Check what may not be used twice, across every inventory at once.

        Host names and mac addresses are unique over the whole installation:
        a host name because it becomes an AD object named after its school
        prefix, a mac address because a machine boots wherever it is plugged
        in. An ip address is unique within a school only - a fileserver
        legitimately carries the same address in every school - so sharing
        one between two schools is reported as a warning.

        :return: Findings on duplicated values
        :rtype: list
        """


        hostnames, macs, ips = {}, {}, {}

        for inventory in self.inventories:
            school = inventory.get('school', 'default-school')
            file = inventory.get('file', '')

            for device in inventory.get('devices', []):
                # One place where a value was used, as 'related' exposes it.
                occurrence = {
                    'school': school,
                    'subject': device.get('hostname', ''),
                    'line': device.get('csvLine'),
                    'file': file,
                }

                # Compared lower cased: sophomorix writes the dns node in
                # lower case and the machine account in upper case out of the
                # same field, so two names differing only by case are the
                # same name.
                hostname = device.get('hostname', '')
                if hostname:
                    hostnames.setdefault(
                        prefixed_hostname(hostname, school).lower(), []
                    ).append(occurrence)

                # Malformed addresses are reported by validate_mac(), and two
                # of them are not "the same address".
                mac = name_checker.normalize_mac(
                    device.get('macRaw', device.get('mac', ''))
                )
                if mac:
                    macs.setdefault(mac, []).append(occurrence)

                ip = device.get('ip', '')
                if ip and ip != DHCP:
                    ips.setdefault(ip, []).append(occurrence)

        findings = []

        for hostname, occurrences in hostnames.items():
            if len(occurrences) > 1:
                findings.append(self._duplicate(
                    ERROR, 'hostname.duplicate', 'hostname', hostname,
                    occurrences, label='name',
                ))

        for mac, occurrences in macs.items():
            if len(occurrences) > 1:
                findings.append(self._duplicate(
                    ERROR, 'mac.duplicate', 'mac', mac, occurrences,
                ))

        for ip, occurrences in ips.items():
            if len(occurrences) < 2:
                continue

            per_school = {}
            for occurrence in occurrences:
                per_school.setdefault(occurrence['school'], []).append(occurrence)

            for school_occurrences in per_school.values():
                if len(school_occurrences) > 1:
                    findings.append(self._duplicate(
                        ERROR, 'ip.duplicate', 'ip', ip, school_occurrences,
                    ))

            if len(per_school) > 1:
                findings.append(self._duplicate(
                    WARNING, 'ip.duplicate_across_schools', 'ip', ip,
                    occurrences, suffix=' in different schools',
                ))

        return findings

    def _duplicate(self, severity, code, field, value, occurrences,
                   label=None, suffix=''):
        """
        One finding about a value used more than once. It is reported on the
        first occurrence, the others being listed in ``related``, so that a
        caller has one line to show and every place to fix.

        :param occurrences: Where the value was used, in the order read
        :type occurrences: list
        :param label: How the value is named in the message, the field itself
                      if not given
        :type label: string
        :rtype: Finding
        """


        names = [prefixed_hostname(o['subject'], o['school']) for o in occurrences]
        first = occurrences[0]

        # A name used twice would otherwise read "pc01, pc01 have the same
        # name pc01".
        if len(set(names)) == 1:
            message = f"{names[0]} is used {len(names)} times{suffix}"
        else:
            message = f"{', '.join(names)} have the same {label or field} {value}{suffix}"

        return Finding(
            severity, code, message,
            field=field, value=value,
            school=first['school'], file=first['file'],
            line=first['line'], subject=first['subject'],
            related=occurrences[1:],
        )

    def _text(self, finding):
        """
        One finding as the single line of the flat report.

        :rtype: string
        """


        # Every place to fix, grouped by file: in a multi-school run, a line
        # number alone does not say which devices.csv it is in.
        lines_per_file = {}
        for occurrence in [{'file': finding.file, 'line': finding.line}] + finding.related:
            if occurrence['line']:
                lines_per_file.setdefault(occurrence['file'], []).append(str(occurrence['line']))
        places = []
        for file, lines in lines_per_file.items():
            numbers = f"line {lines[0]}" if len(lines) == 1 else f"lines {', '.join(lines)}"
            places.append(f"{file}, {numbers}" if file else numbers)
        location = f" ({'; '.join(places)})" if places else ""

        # The subject is only added when the message does not already start
        # with it, as the hostname rules and the duplicates do.
        host = ""
        if finding.subject:
            name = prefixed_hostname(finding.subject, finding.school)
            if not finding.message.startswith((f"{name} ", f"{name},")):
                host = f"{name}: "

        return f"{finding.severity.upper()}: {host}{finding.message}{location}"
