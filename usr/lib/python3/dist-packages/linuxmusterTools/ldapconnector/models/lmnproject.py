from dataclasses import dataclass, field, asdict
from datetime import datetime
from ..urls import router as lr


@dataclass
class LMNProject:
    cn: str
    description: str
    distinguishedName: str
    mail: list
    member: list
    name: str
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAddMailQuota: list
    sophomorixAddQuota: list
    sophomorixAdminGroups: list
    sophomorixAdmins: list
    sophomorixCreationDate: str # datetime
    sophomorixHidden: bool
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

    def __post_init__(self):
        self.dn = self.distinguishedName

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

        members = set(self.sophomorixMembers)
        admins = set(self.sophomorixAdmins)

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

        self.membersCount = len(set(members))
        self.all_members = members

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

        self.adminsCount = len(set(admins))
        self.all_admins = admins