from dataclasses import dataclass, field, asdict
from ..urls import router as lr
from .lmnobject import LMNObject


@dataclass
class LMNGroup:
    cn: str
    description: str
    displayName: str
    distinguishedName: str
    member: list
    memberOf: list
    name: str
    objectClass: list
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAdminClass: str
    sophomorixCreationDate: str
    sophomorixHidden: bool
    sophomorixIntrinsicMulti1: list
    sophomorixJoinable: bool
    sophomorixMembers: list
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
    sophomorixType: str
    dn: str = field(init=False)
    all_members: list = field(init=False)
    membersCount: int = field(init=False)

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.all_members = []
        self.membersCount = -1

    def asdict(self):
        return asdict(self)

    def get_all_members(self):
        """
        Set a members and admins list by recursively scanning all groups and their members which are members
        or admins of this project.

        This is not called as post init because of nested projects. So it's necessary to call this method
        afterwards:

        p = lr.get('/projects/p_test', dict=False)
        p.get_all_members()
        """

        members = set()
        to_scan = []

        for dn in self.member:
            details = lr.get(f'/dn/{dn}')
            if 'person' in details["objectClass"]:
                members.add(details['cn'])
            elif 'group' in details["objectClass"]:
                to_scan.append(details['cn'])

        already_scanned = []

        while to_scan:
            group = to_scan[0]
            if group not in already_scanned:
                already_scanned.append(group)

                # I assume a group is a project or a schoolclass
                if group.startswith('p_'):
                    group_details = lr.get(f'/projects/{group}', attributes=['sophomorixMembers', 'sophomorixMemberGroups'])
                    group_members = set(group_details.get('sophomorixMembers', []))
                    subgroups = group_details.get('sophomorixMemberGroups', [])

                    # Subgroups must eventually come in the scan list
                    for subgroup in subgroups:
                        if subgroup not in already_scanned:
                            to_scan.append(subgroup)
                else:
                    group_members = set(lr.get(f'/schoolclasses/{group}').get('sophomorixMembers', []))

                members = members.union(group_members)

            to_scan = to_scan[1:]

        self.membersCount = len(members)
        self.all_members = list(members)
