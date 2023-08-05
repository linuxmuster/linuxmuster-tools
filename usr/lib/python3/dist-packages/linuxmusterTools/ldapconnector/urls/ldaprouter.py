import re

from linuxmusterTools.ldapconnector.connector import LdapConnector


class LMNLdapRouter:
    def __init__(self):
        self.lc = LdapConnector()
        self.methods = [getattr(self,method) for method in dir(self) if method.startswith('get_')]
        self.urls = {}

    def get(self, url, **kwargs):
        """
        Parse all urls and find the correct API to handle the request.
        """

        for url_model, func in self.urls.items():
            match = func.url_pattern.match(url)
            if match:
                data = match.groupdict()
                ldap_filter = func(**data)

                if func.type == 'single':
                    return self.lc.get_single(func.model, ldap_filter, **kwargs)

                if func.type == 'collection':
                    return self.lc.get_collection(func.model, ldap_filter, **kwargs)
        raise Exception('Request unknown')

    def single(self, pattern, model):
        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            self.urls[f.url_pattern] = f
            return f
        return decorator

    def collection(self, pattern, model):
        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            self.urls[f.url_pattern] = f
            return f
        return decorator

router = LMNLdapRouter()