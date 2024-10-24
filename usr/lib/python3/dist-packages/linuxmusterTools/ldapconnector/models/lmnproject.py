from dataclasses import dataclass, field
from ..urls import router as lr
from .common import LMNParent


@dataclass
class LMNProject(LMNParent):
    cn: str
    description: str
    displayName: str
    distinguishedName: str
    mail: list
    member: list
    name: str
    objectClass: list
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAddMailQuota: list
    sophomorixAddQuota: list
    sophomorixAdminGroups: list
    sophomorixAdmins: list
    sophomorixCreationDate: str # datetime
    sophomorixHidden: bool
    sophomorixIntrinsicMulti1: list
    sophomorixJoinable: bool
    sophomorixMailAlias: bool
    sophomorixMailList: bool
    sophomorixMailQuota: list
    sophomorixMaxMembers: int
    sophomorixMemberGroups: list
    sophomorixMembers: list
    sophomorixQuota: list
    sophomorixSchoolname: str
    sophomorixStatus: str
    sophomorixType: str
    dn: str = field(init=False)
    all_members: list = field(init=False)
    all_admins: list = field(init=False)
    membersCount: int = field(init=False)
    adminsCount: int = field(init=False)

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.all_admins = []
        self.all_members = []
        self.membersCount = -1
        self.adminsCount = -1

    def get_all_members(self):
        """
        Set a members and admins list by recursively scanning all groups and their members which are members
        or admins of this project.

        This is not called as post init because of nested projects. So it's necessary to call this method
        afterwards:

        p = lr.get('/projects/p_test', dict=False)
        p.get_all_members()
        """

        members = set(self.sophomorixMembers)
        admins = set(self.sophomorixAdmins)

        ## Unfortunately there's members which are not in sophomorixMembers
        for dn in self.member:
            details = lr.get(f'/dn/{dn}')
            # TODO : handles group too ?
            if 'person' in details["objectClass"]:
                members.add(details['cn'])

        to_scan = self.sophomorixMemberGroups
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

        to_scan = self.sophomorixAdminGroups
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

                admins = admins.union(group_members)

            to_scan = to_scan[1:]

        self.adminsCount = len(admins)
        self.all_admins = list(admins)