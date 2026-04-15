"""
LINBO Wake-on-LAN — send magic packets to wake up hosts.

Supports direct UDP broadcast and optional Networkbox API proxy.
"""

import logging
import os
import re
import socket


logger = logging.getLogger(__name__)

def create_magic_packet(mac_address: str) -> bytes:
    """Create IEEE 802.3 Wake-on-LAN magic packet.

    6 bytes of 0xFF followed by the MAC address repeated 16 times = 102 bytes.

    Args:
        mac_address: MAC address (XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)

    Returns:
        102-byte magic packet

    Raises:
        ValueError: If MAC address is invalid
    """


    mac = re.sub(r"[:\-]", "", mac_address)
    if len(mac) != 12 or not re.match(r"^[0-9a-fA-F]+$", mac):
        raise ValueError(f"Invalid MAC address: {mac_address}")

    mac_bytes = bytes.fromhex(mac)
    return b"\xff" * 6 + mac_bytes * 16


def send_wol(
    mac_address: str,
    broadcast: str | None = None,
    port: int = 9,
    count: int = 3,
) -> dict:
    """Send Wake-on-LAN packet via UDP broadcast.

    Args:
        mac_address: Target MAC address
        broadcast: Broadcast address (default: WOL_BROADCAST_ADDRESS env or 255.255.255.255)
        port: UDP port (default: 9)
        count: Number of packets to send (default: 3)

    Returns:
        Dict with macAddress, packetsSent, broadcastAddress, port
    """


    if broadcast is None:
        broadcast = os.environ.get("WOL_BROADCAST_ADDRESS", "255.255.255.255")

    packet = create_magic_packet(mac_address)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        for _ in range(count):
            sock.sendto(packet, (broadcast, port))
    finally:
        sock.close()

    return {
        "macAddress": mac_address,
        "packetsSent": count,
        "broadcastAddress": broadcast,
        "port": port,
    }


def send_wol_bulk(
    mac_addresses: list[str],
    broadcast: str | None = None,
    port: int = 9,
    count: int = 3,
) -> dict:
    """Send Wake-on-LAN to multiple hosts.

    Returns:
        Dict with total, successful, failed, and per-host results
    """
    results = []
    successful = 0
    failed = 0

    for mac in mac_addresses:
        try:
            send_wol(mac, broadcast=broadcast, port=port, count=count)
            results.append({"macAddress": mac, "success": True, "error": None})
            successful += 1
        except Exception as e:
            results.append({"macAddress": mac, "success": False, "error": str(e)})
            failed += 1

    return {
        "total": len(mac_addresses),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
