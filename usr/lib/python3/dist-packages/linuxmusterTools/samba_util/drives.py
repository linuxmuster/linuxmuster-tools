import logging
from dataclasses import dataclass, field, asdict
import xml.etree.ElementTree as ElementTree


@dataclass
class Drive:
    disabled: bool
    filters: dict
    label: str
    letter: str
    properties: dict
    userLetter: str
    id: str = field(init=False)

    def __post_init__(self):
        self.id = None
        if self.properties['path'] is not None:
            self.id = self.properties['path'].split('\\')[-1]

    # def visible(self, user):
        # TODO: this was written with a wrong interpretation of filters,
        # must be rewritten with more informations from the user (groups
        # membership, role, etc ...).
        # The parameter user should be a user object from ldapreader

        # if self.disabled:
            # Disabled for all
        #     return False
        #
        # if not self.filters:
            # No filter, available for all
        #     return True
        #
        # for filter_role, rules in self.filters.items():
        #     if filter_role == role:
        #         if rules['bool'] == 'AND' and not rules['negation']:
        #             return True
        #
        # Default policy
        # return False

class DriveManager:
    """
    Object to store data from Drives.xml
    """

    def __init__(self, policy_path):
        try:
            self.policy = policy_path.split('/')[-1]
            self.path = f'{policy_path}/User/Preferences/Drives/Drives.xml'
        except Exception:
            logging.error(f"{policy_path} is not a valid policy path.")
            self.path = ''
        self.usedLetters = []
        self.load()

    def load(self):
        """
        Parse the Drives.xml in the policy directory in order to get all shares
        properties.
        """

        self.drives = []

        try:
            self.tree = ElementTree.parse(self.path)
        except FileNotFoundError:
            return

        for drive in self.tree.findall('Drive'):
            properties = self._parseProperties(drive)
            filters = self._parseFilters(drive)
            disabled = bool(int(drive.attrib.get('disabled', '0')))

            self.usedLetters.append(properties['letter'])
            self.drives.append(
                Drive(
                    disabled=disabled,
                    filters=filters,
                    label=properties['label'],
                    letter=properties['letter'],
                    properties=properties,
                    userLetter=properties['useLetter'],
                )
            )

    @staticmethod
    def _parseProperties(drive):
       properties = {}
       # It should be max one properties node
       for prop in drive.findall('Properties'):
            properties['useLetter'] = bool(int(prop.get('useLetter', '0')))
            properties['letter'] = prop.get('letter', '')
            properties['label'] = prop.get('label', 'Unknown')
            properties['path'] = prop.get('path', None)
       return properties

    @staticmethod
    def _parseFilters(drive):
        filters = {}
        # It should be max one node Filters
        for filter in drive.findall('Filters'):
            for filtergroup in filter.findall('FilterGroup'):
                name = filtergroup.get('name', '').split('\\')[1]
                values = {
                    'bool': filtergroup.get("bool", ""),
                    'negation': filtergroup.get("not", '0') != '0'
                }
                # If the same role appears more than one time, the last
                # filtergroup node will overwrite the precedent one
                filters[name] = values
        return filters

    def save(self, content):
        """
        Save all configuration and properties from the drives and then reload
        the configuration.

        :param content: All drives configuration and properties
        :type content: dict
        """

        self.tree.write(f'{self.path}.bak', encoding='utf-8', xml_declaration=True)

        for drive in self.tree.findall('Drive'):
            for prop in drive.findall('Properties'):
                for newDrive in content:
                    if newDrive['properties']['label'] == prop.get('label', 'Unknown'):
                        prop.set('letter', newDrive['properties']['letter'])
                        prop.set('useLetter', str(int(newDrive['properties']['useLetter'])))
                        drive.set('disabled', str(int(newDrive['disabled'])))

        self.tree.write(self.path, encoding='utf-8', xml_declaration=True)
        self.load()

    def aslist(self):
        return [asdict(d) for d in self.drives]
