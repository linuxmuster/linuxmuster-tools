import ssl
import socket
from datetime import datetime

class DomCert:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.load()

    def load(self):
        self.valid = None
        self.notAfter = None
        self.notAfter_timestamp = None
        self.cert = None

        self._get_cert()
        self._get_limit()

    def _get_cert(self):
        """
        Get standard SSL cert from hostname:port
        """


        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(socket.socket(), server_hostname=self.hostname)
        s.settimeout(10)
        s.connect((self.hostname, self.port))
        self.cert = s.getpeercert()
        s.close()

    def _get_limit(self):
        self.notAfter = self.cert['notAfter']
        self.notAfter_timestamp = datetime.strptime(self.notAfter,"%b %d %H:%M:%S %Y GMT")
        self.valid = (self.notAfter_timestamp - datetime.now()).days > 0

    def isvalid(self):
        self.load()
        return self.valid

    def expires(self):
        self.load()
        if self.valid:
            return f"{(self.notAfter_timestamp - datetime.now()).days} days ({self.notAfter})"

        return f"Expired since {self.notAfter}"
