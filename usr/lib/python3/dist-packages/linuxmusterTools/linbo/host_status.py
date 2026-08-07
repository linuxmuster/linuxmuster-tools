"""
LINBO Host Status Scanner — TCP port probing for online detection.

Probes port 2222 (Dropbear SSH on LINBO clients) to determine
if a host is online. Supports concurrent scanning.

Also classifies a host's boot state (Off, Linbo, OS Linux, OS Windows,
OS Unknown) from the state of ports 2222/22/135, without depending on
nmap. Since there is no separate host-discovery/ping step here (unlike
nmap), a host that doesn't answer on any of the three ports is reported
as 'Off' directly, instead of the 'Off' vs 'No response' distinction the
nmap-based webui implementation made.
"""

import asyncio
import logging
import socket
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_PORT = 2222
DEFAULT_TIMEOUT = 2.0
DEFAULT_CONCURRENCY = 20


async def probe_host(ip: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Test if a host is reachable via TCP connect.

    Args:
        ip: Target IP address
        port: TCP port to probe (default: 2222)
        timeout: Connection timeout in seconds (default: 2.0)

    Returns:
        True if host is reachable, False otherwise
    """

    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError):
        return False


async def scan_hosts(
    hosts: list[dict],
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict]:
    """Scan multiple hosts concurrently for online status.

    Args:
        hosts: List of host dicts with at least 'ip' and 'mac' keys
        port: TCP port to probe
        timeout: Per-host connection timeout
        concurrency: Max concurrent probes

    Returns:
        List of {mac, ip, hostname, online, lastSeen} dicts
    """

    semaphore = asyncio.Semaphore(concurrency)
    now = datetime.now(timezone.utc).isoformat()

    async def _probe(host: dict) -> dict:
        async with semaphore:
            ip = host.get("ip")
            if not ip:
                return {
                    "mac": host.get("mac"),
                    "ip": None,
                    "hostname": host.get("hostname"),
                    "online": False,
                    "lastSeen": None,
                }
            online = await probe_host(ip, port=port, timeout=timeout)
            return {
                "mac": host.get("mac"),
                "ip": ip,
                "hostname": host.get("hostname"),
                "online": online,
                "lastSeen": now if online else None,
            }

    tasks = [_probe(h) for h in hosts]
    return await asyncio.gather(*tasks)


def scan_hosts_sync(
    hosts: list[dict],
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict]:
    """
    Synchronous wrapper for scan_hosts (for use outside async context).
    """

    return asyncio.run(scan_hosts(hosts, port=port, timeout=timeout, concurrency=concurrency))


CLASSIFY_PORTS = (2222, 22, 135)


def probe_port_state(ip: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Probe a single TCP port and classify its state.

    Plain blocking socket, not asyncio: this is meant to be called from
    gevent-monkey-patched code (e.g. the webui), where a blocking
    socket.create_connection() is cooperative for free, while an asyncio
    event loop would not be.

    Returns:
        'open' if the connection succeeds, 'closed' if the host actively
        refuses it, 'filtered' if it doesn't respond at all (timeout or
        unreachable) — mirroring nmap's port states without shelling out to it.
    """

    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return "open"
    except ConnectionRefusedError:
        return "closed"
    except OSError:
        return "filtered"


def classify_os(ports: dict[int, str]) -> str:
    """Classify a host's boot state from its port states.

    :param ports: Dict mapping port number (2222, 22, 135) to its state
        ('open', 'closed' or 'filtered').
    :return: One of 'Off', 'Linbo', 'OS Linux', 'OS Windows', 'OS Unknown'.
    """

    if all(state == "filtered" for state in ports.values()):
        return "Off"

    if {port for port, state in ports.items() if state == "open"} == {2222}:
        return "Linbo"
    if ports.get(22) in ("open", "filtered") and ports.get(135) != "open":
        return "OS Linux"
    if ports.get(135) in ("open", "filtered") and ports.get(22) != "open":
        return "OS Windows"
    return "OS Unknown"


def classify_host(ip: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Probe a host on ports 2222/22/135 and classify its boot state.

    Returns:
        One of 'Off', 'Linbo', 'OS Linux', 'OS Windows', 'OS Unknown'.
    """

    ports = {port: probe_port_state(ip, port, timeout) for port in CLASSIFY_PORTS}
    return classify_os(ports)
