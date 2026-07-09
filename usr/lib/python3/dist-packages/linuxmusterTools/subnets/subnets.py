import ipaddress
import logging
import subprocess
from pathlib import Path

from ..lmnfile import LMNFile
from ..common.timestamps import get_utc_mtime


logger = logging.getLogger(__name__)

# Single, school-independent file, managed by linuxmuster-import-subnets.
SUBNETS_PATH = '/etc/linuxmuster/subnets.csv'
IMPORT_COMMAND = 'linuxmuster-import-subnets'

# Valid values for the SETUP-Flag column (empty means "regular subnet").
SETUP_FLAGS = ['', 'SETUP']


class Subnets:
    """
    Read and validate the global subnets definition file
    (/etc/linuxmuster/subnets.csv), which is imported into the DHCP, ntp and
    netplan configuration by linuxmuster-import-subnets.

    Unlike devices.csv, subnets.csv is not per-school: there is exactly one file
    for the whole server.
    """

    def __init__(self, path=SUBNETS_PATH):
        self.path = path
        self.load()

    def load(self):
        self.subnets = []

        with LMNFile(self.path, 'r') as subnets_csv:
            for subnet in subnets_csv.read():
                # Skip comment lines and empty lines.
                network = (subnet.get('network') or '').strip()
                if not network or network.startswith('#'):
                    continue

                self.subnets.append(subnet)

        self.networks = list({s['network'] for s in self.subnets if s.get('network')})
        self.csv_mtime = get_utc_mtime(Path(self.path))

    def filter(self, networks=[]):
        """
        Filter the subnets list by network (e.g. '10.0.0.0/16').
        """

        if networks:
            return [subnet for subnet in self.subnets if subnet['network'] in networks]
        return self.subnets

    def get_subnet(self, network):
        for subnet in self.subnets:
            if subnet['network'] == network:
                return subnet
        return None

    def check_conf(self):
        """
        Validate the content of subnets.csv. Returns a list of human readable
        error messages, or False if everything is valid.
        """

        report = []

        network_rev = {}
        for subnet in self.subnets:
            network = subnet.get('network', '')

            if network in network_rev:
                network_rev[network] += 1
            else:
                network_rev[network] = 1

            # network must be a valid CIDR (e.g. 10.0.0.0/16).
            try:
                net = ipaddress.ip_network(network, strict=True)
            except ValueError:
                report.append(f"{network} is not a valid network in CIDR notation")
                net = None

            # routerIp, beginRange and endRange must be valid IPs inside network.
            for field in ['routerIp', 'beginRange', 'endRange']:
                value = (subnet.get(field) or '').strip()
                if not value:
                    report.append(f"{network}: {field} must not be empty")
                    continue
                try:
                    ip = ipaddress.ip_address(value)
                except ValueError:
                    report.append(f"{value} is not a valid ip address ({field} of {network})")
                    continue
                if net is not None and ip not in net:
                    report.append(f"{value} ({field}) is not part of network {network}")

            # nameServer and nextServer are optional, but must be valid IPs if set.
            for field in ['nameServer', 'nextServer']:
                value = (subnet.get(field) or '').strip()
                if value:
                    try:
                        ipaddress.ip_address(value)
                    except ValueError:
                        report.append(f"{value} is not a valid ip address ({field} of {network})")

            setup_flag = (subnet.get('setupFlag') or '').strip()
            if setup_flag not in SETUP_FLAGS:
                report.append(f"{setup_flag} is not a valid setup flag for {network} (allowed: SETUP or empty)")

        for network, count in network_rev.items():
            if count > 1:
                report.append(f"{network} is defined {count} times")

        if report:
            return report

        return False


def import_subnets():
    """
    Run linuxmuster-import-subnets, which regenerates the DHCP, ntp and netplan
    configuration from /etc/linuxmuster/subnets.csv and restarts the affected
    services.

    Returns a dict with the return code and the captured stdout/stderr.
    """

    logger.info("Running %s", IMPORT_COMMAND)
    results = subprocess.run(
        [IMPORT_COMMAND],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return {
        'returncode': results.returncode,
        'output': results.stdout.decode(errors='replace'),
    }
