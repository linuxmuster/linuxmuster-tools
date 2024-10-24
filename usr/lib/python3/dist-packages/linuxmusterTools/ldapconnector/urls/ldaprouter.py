import re
import ldap
import csv
import logging
from datetime import datetime

from linuxmusterTools.ldapconnector.ldap_reader import LdapReader


# This marker will be replaced by the selected school, or default-school
SCHOOL_MARKER = "##SCHOOL_MARKER##"

class LMNLdapRouter:
    def __init__(self):
        self.lr = LdapReader()
        self.urls = {}

    def _find_method(self, url):
       for url_model, func in self.urls.items():
            match = func.url_pattern.match(url)
            if match:
                data = match.groupdict()
                return func, data
       raise Exception(f'Requested search {url} unknown')

    def get(self, url, **kwargs):
        """
        Parse all urls and find the right method to handle the request.
        """

        func, data = self._find_method(url)
        ldap_filter = func(**data)

        # Replace selected school in the subdn where we are searching
        if 'school' in kwargs:
            school = kwargs['school']
        else:
            school = 'default-school'

        subdn = func.subdn

        # Global search for globaladmin if the subdn is restricted to a school
        # search like "ou=default-school,ou=schools,".
        # If the subdn is more specific in a school, like
        # "ou=management,ou=default-school,ou=schools,", then the parameter
        # school is necessary, and we throw an error when missing.

        if subdn:
            if school == 'global':
                subdn = "OU=SCHOOLS,"
            else:
                subdn = subdn.replace(SCHOOL_MARKER, school)

        if func.type == 'single':
            return self.lr.get_single(func.model, ldap_filter, scope=func.scope, subdn=subdn, dn_filter=func.dn_filter, **kwargs)

        if func.type == 'collection':
            return self.lr.get_collection(func.model, ldap_filter, scope=func.scope, subdn=subdn, dn_filter=func.dn_filter, **kwargs)

    def getval(self, url, attribute, **kwargs):

        if isinstance(attribute, str):
            attrs = [attribute]
        else:
            raise Exception(f"Attribute {attribute} should be a string.")

        results = self.get(url, attributes=attrs, dict=dict, **kwargs)

        if isinstance(results, list):
            # results is a collection
            return [result.get(attribute, None) for result in results]
        else:
            return results.get(attribute, None)

    def getvalues(self, url, attributes, dict=True, **kwargs):

        if isinstance(attributes, list):
            attrs = attributes
        else:
            raise Exception(f"Attributes {attributes} should be a list of valid attributes.")

        results = self.get(url, attributes=attrs, dict=dict, **kwargs)

        if isinstance(results, list):
            # results is a collection
            if dict:
                return [{attr: result.get(attr, None) for attr in attrs} for result in results]
            else:
                return [{attr: getattr(result, attr, None) for attr in attrs} for result in results]
        else:
            if dict:
                return {attr: results.get(attr, None) for attr in attrs}
            else:
                return {attr: getattr(results, attr, None) for attr in attrs}

    def ascsv(self, url, delimiter=";", csvfile=None, attributes=[], header=True, **kwargs):
        if not csvfile:
            # TODO: find a better path
            obj_type = url.split('/')[1]
            now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            csvfile = f'/tmp/export_csv_{obj_type}_{now}.csv'

        data = self.get(url, attributes=attributes, dict=True, **kwargs)
        if not isinstance(data, list):
            data = [data]

        headers = list(data[0].keys())

        with open(csvfile, 'w') as csv_io:
            csv_writer = csv.writer(csv_io, delimiter=delimiter)

            if header:
                csv_writer.writerow(headers)

            for entry in data:
                csv_writer.writerow([entry[field] for field in headers])

        logging.info(f"CSV file successfully exported to {csvfile}")
        print(f"CSV file successfully exported to {csvfile}")

    def add_url(self, url, method):
        """
        Check collisions between URLs before adding to self.urls.

        :param url: Regexp to match
        :type url: re.pattern
        :param method: Method to run
        :type method: function
        """

        if url in self.urls:
            logging.warning(f"URL {url} already listed in the methods, not adding it!")
        else:
            self.urls[url] = method

    def single(self, pattern, model, subdn='', dn_filter='', level="subtree"):
        """
        Search a single entry in the whole subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            if level == "single":
                f.scope = ldap.SCOPE_ONELEVEL
            else:
                f.scope = ldap.SCOPE_SUBTREE
            f.subdn = subdn
            f.dn_filter = dn_filter
            self.add_url(f.url_pattern, f)
            return f
        return decorator

    def collection(self, pattern, model, subdn='', dn_filter='', level="subtree"):
        """
        Search multiple entries in the whole subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            if level == "single":
                f.scope = ldap.SCOPE_ONELEVEL
            else:
                f.scope = ldap.SCOPE_SUBTREE
            f.subdn = subdn
            f.dn_filter = dn_filter
            self.add_url(f.url_pattern, f)
            return f
        return decorator

router = LMNLdapRouter()