"""
Sanity tests for linuxmusterTools.lmnconfig.server.

server.py computes SERVER_HOSTNAME and SERVER_IP as module-level side
effects at import time via socket.gethostname()/socket.gethostbyname_ex(),
using this machine's real network configuration. Since the module is only
imported once per test process, that computation cannot be meaningfully
mocked or re-triggered per test case here (same constraint as samba.py's
import-time Samba lookups). These are therefore intentionally light
sanity checks on the already-computed module attributes, not a real test
of the socket-lookup logic itself.
"""

from linuxmusterTools.lmnconfig import server


def test_server_hostname_is_a_non_empty_string():
    assert isinstance(server.SERVER_HOSTNAME, str)
    assert server.SERVER_HOSTNAME != ''


def test_server_ip_is_a_non_empty_string():
    # Either a real IP resolved for this host, or the documented fallback
    # message when no non-loopback address could be found.
    assert isinstance(server.SERVER_IP, str)
    assert server.SERVER_IP != ''


def test_server_ip_is_not_a_loopback_address_when_resolved():
    # If SERVER_IP looks like an IP (not the fallback message), it must not
    # start with 127., since the code explicitly filters those out.
    if server.SERVER_IP.count('.') == 3 and server.SERVER_IP.replace('.', '').isdigit():
        assert not server.SERVER_IP.startswith('127.')
