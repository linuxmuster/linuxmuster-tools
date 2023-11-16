import subprocess
import xml.etree.ElementTree as ElementTree
from concurrent import futures

from .devices import Devices


class UPChecker:
    def __init__(self, school='default-school'):
        self.devicesmgr = Devices()
        self.devices = self.devicesmgr.clients

    def checkhost(self, hostname):
        to_check = self.devicesmgr.get_client(hostname)

        if to_check:
            return self.test_online(to_check)
        return {}

    def check(self, groups=[]):
        to_check = self.devicesmgr.get_clients(groups=groups)

        results = {}
        with futures.ThreadPoolExecutor() as executor:
            for result in executor.map(self.test_online, to_check):
                ip = list(result.keys())[0]
                results[ip] = result[ip]
        return results

    def test_online(self, device):
        """
        Launch a nmap on a host to test if the os is up, and return OS type.

        :param device: device entry in devices.csv
        :type device: dict
        :return: OS type (Off, Linbo, OS Linux, OS Windows, OS Unknown)
        :rtype: string
        """

        command=["nmap", "-p", "2222,22,135", device['ip'], "-oX", "-"]
        r = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False).stdout.read()
        xmlRoot = ElementTree.fromstring(r)

        numberOfOnlineHosts = int(xmlRoot.find("runstats").find("hosts").attrib["up"])
        if numberOfOnlineHosts == 0:
            return {device['ip']: "Off"}

        ports = {}
        scannedPorts = xmlRoot.find("host").find("ports").findall("port")

        numberOfFilteredPorts = 0

        for scannedPort in scannedPorts:
            portNumber = scannedPort.attrib["portid"]
            portState = scannedPort.find("state").attrib["state"]
            ports[portNumber] = portState

            numberOfFilteredPorts += int(portState == "filtered")

        if numberOfFilteredPorts == 3:
            # All ports filtered, no answer from the host,
            # likely because the host is down and the firewall doesn't respond.
            return {device['ip']: "No response"}

        return {device['ip']: self.get_os_from_ports(ports)}

    def get_os_from_ports(self, ports):
        """
        Convert a dict of ports to an OS string.

        :param openPorts: The dict of open ports (key: port number, value: port state)
        :type openPorts: dict
        :return: OS type (Linbo, OS Linux, OS Windows, OS Unknown)
        :rtype: string
        """

        if self.is_port_signature_linbo(ports):
            return "Linbo"
        if self.is_port_signature_linux(ports):
            return "OS Linux"
        if self.is_port_signature_windows(ports):
            return "OS Windows"
        return "OS Unknown"

    @staticmethod
    def is_port_signature_linbo(ports):
        """
        Check if a dict of ports belongs to a Linbo host.
        The criteria for Linbo is, that ONLY port 2222 is open

        :param openPorts: The dict of open ports (key: port number, value: port state)
        :type openPorts: dict
        :return: Whether it's a Linbo host
        :rtype: bool
        """

        openPortNumbers = []
        for port in ports:
            if ports[port] == "open":
                openPortNumbers.append(port)

        return (
            "2222" in openPortNumbers
            and len(openPortNumbers) == 1
        )

    @staticmethod
    def is_port_signature_linux(ports):
        """
        Check if a dict of ports belongs to a Linux host.
        The criteria for Linux is, that port 22 is open and 135 is closed.

        :param openPorts: The dict of open ports (key: port number, value: port state)
        :type openPorts: dict
        :return: Whether it's a Linux host
        :rtype: bool
        """

        return (
            "22" in ports
            and ports["22"] in ["open", "filtered"]
            and (
                "135" not in ports
                or ports["135"] != "open"
            )
        )

    @staticmethod
    def is_port_signature_windows(ports):
        """
        Check if a dict of ports belongs to a Windows host.
        The criteria for Windows is, that port 135 is open and 22 is not open.

        :param openPorts: The dict of open ports (key: port number, value: port state)
        :type openPorts: dict
        :return: Whether it's a Windows host
        :rtype: bool
        """

        return (
            "135" in ports
            and ports["135"] in ["open", "filtered"]
            and (
                "22" not in ports
                or ports["22"] != "open"
            )
        )