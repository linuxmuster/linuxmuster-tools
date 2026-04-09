"""
LINBO Host Status Scanner — TCP port probing for online detection.

Probes port 2222 (Dropbear SSH on LINBO clients) to determine
if a host is online. Supports concurrent scanning.
"""

import asyncio
import logging
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
    """Synchronous wrapper for scan_hosts (for use outside async context)."""
    return asyncio.run(scan_hosts(hosts, port=port, timeout=timeout, concurrency=concurrency))
