"""
LINBO SSH Service — execute commands on LINBO clients via SSH.

Uses the system ssh client. Key loading is lazy: the private key is loaded
on first use, not at module import time.

Default connection: root@host:2222 with RSA key from
/etc/linuxmuster/linbo/ssh_host_rsa_key_client
"""

import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Key paths
_KEY_PATH = os.environ.get(
    "LINBO_CLIENT_SSH_KEY",
    "/etc/linuxmuster/linbo/ssh_host_rsa_key_client",
)
_SSH_BIN = os.environ.get("LINBO_CLIENT_SSH_BIN", "ssh")
_SSH_PORT = int(os.environ.get("LINBO_CLIENT_SSH_PORT", "2222"))
_SSH_TIMEOUT = int(os.environ.get("SSH_TIMEOUT", "10"))
_MAX_OUTPUT = 10 * 1024 * 1024  # 10 MB

# Lazy-loaded key cache
_cached_key = None

# Validation patterns for shell-safe parameters
SAFE_OSNAME_RE = re.compile(r"^[A-Za-z0-9 ._-]{1,100}$")
SAFE_PARTITION_RE = re.compile(r"^/dev/[a-z]{2,8}[0-9]{1,3}$")
SAFE_DOWNLOAD_TYPE_RE = re.compile(r"^(rsync|multicast|torrent)$")


def _get_private_key_path() -> str:
    """Get SSH private key path. Tries primary, then fallback.

    Returns:
        Path to the private key file

    Raises:
        FileNotFoundError: If no key file is available
    """
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    if Path(_KEY_PATH).is_file():
        _cached_key = _KEY_PATH
        logger.info("Loaded LINBO client key from %s", _KEY_PATH)
        return _cached_key

    fallback = os.environ.get("SSH_PRIVATE_KEY")
    if fallback and Path(fallback).is_file():
        _cached_key = fallback
        logger.warning("Using fallback SSH key: %s", fallback)
        return _cached_key

    raise FileNotFoundError(
        f"SSH private key not available. Expected: {_KEY_PATH}"
    )


def _build_ssh_command(
    host: str,
    command: str,
    port: int | None = None,
    timeout: float | None = None,
) -> list[str]:
    """Build the ssh command used for remote execution."""
    if port is None:
        port = _SSH_PORT
    if timeout is None:
        timeout = _SSH_TIMEOUT

    key_path = _get_private_key_path()
    connect_timeout = max(int(timeout), 1)

    return [
        _SSH_BIN,
        "-i",
        key_path,
        "-p",
        str(port),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        f"root@{host}",
        command,
    ]


def execute_command(
    host: str,
    command: str,
    port: int | None = None,
    timeout: float | None = None,
) -> dict:
    """Execute a command on a remote host via SSH.

    Args:
        host: Target hostname or IP
        command: Shell command to execute
        port: SSH port (default: 2222)
        timeout: Connection timeout in seconds

    Returns:
        {stdout, stderr, code}
    """
    if timeout is None:
        timeout = _SSH_TIMEOUT

    result = subprocess.run(
        _build_ssh_command(host, command, port=port, timeout=timeout),
        capture_output=True,
        text=True,
        timeout=max(timeout, 1),
    )

    return {
        "stdout": result.stdout[:_MAX_OUTPUT],
        "stderr": result.stderr[:_MAX_OUTPUT],
        "code": result.returncode,
    }


def execute_commands(
    host: str,
    commands: list[str],
    port: int | None = None,
    timeout: float | None = None,
    continue_on_error: bool = False,
) -> list[dict]:
    """Execute multiple commands sequentially.

    Args:
        host: Target hostname or IP
        commands: List of shell commands
        continue_on_error: Continue even if a command fails

    Returns:
        List of {command, success, stdout, stderr, code} dicts
    """
    results = []
    for cmd in commands:
        try:
            result = execute_command(host, cmd, port=port, timeout=timeout)
            results.append({
                "command": cmd,
                "success": result["code"] == 0,
                **result,
            })
            if result["code"] != 0 and not continue_on_error:
                break
        except Exception as e:
            results.append({
                "command": cmd,
                "success": False,
                "error": str(e),
                "code": -1,
            })
            if not continue_on_error:
                break
    return results


def test_connection(host: str, port: int | None = None) -> dict:
    """Test SSH connectivity to a host.

    Returns:
        {success, connected} or {success: False, error}
    """
    try:
        result = execute_command(host, 'echo "connected"', port=port, timeout=5)
        return {
            "success": True,
            "connected": result["stdout"].strip() == "connected",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _validate_param(value: str, name: str, pattern: re.Pattern) -> None:
    """Validate a parameter for shell safety."""
    if not pattern.match(value):
        raise ValueError(f'Invalid {name}: "{value}"')


def execute_linbo_command(host: str, linbo_command: str, params: dict | None = None) -> dict:
    """Execute a LINBO command on a host.

    Supported commands: sync, start, reboot, shutdown, halt, initcache, partition, format

    Args:
        host: Target hostname or IP
        linbo_command: LINBO command name
        params: Optional parameters (osName, forceNew, downloadType, partition)

    Returns:
        {stdout, stderr, code}
    """
    if params is None:
        params = {}

    def _build_cmd() -> str:
        if linbo_command == "sync":
            cmd = "linbo_cmd synconly"
            if params.get("forceNew"):
                cmd += " -f"
            if params.get("osName"):
                _validate_param(params["osName"], "osName", SAFE_OSNAME_RE)
                cmd += " " + params["osName"]
            return cmd

        if linbo_command == "start":
            cmd = "linbo_cmd start"
            if params.get("osName"):
                _validate_param(params["osName"], "osName", SAFE_OSNAME_RE)
                cmd += " " + params["osName"]
            return cmd

        if linbo_command in ("reboot", "shutdown", "halt", "partition"):
            return "linbo_cmd " + linbo_command

        if linbo_command == "initcache":
            cmd = "linbo_cmd initcache"
            if params.get("downloadType"):
                _validate_param(params["downloadType"], "downloadType", SAFE_DOWNLOAD_TYPE_RE)
                cmd += " " + params["downloadType"]
            return cmd

        if linbo_command == "format":
            cmd = "linbo_cmd format"
            if params.get("partition"):
                _validate_param(params["partition"], "partition", SAFE_PARTITION_RE)
                cmd += " " + params["partition"]
            return cmd

        raise ValueError(f"Unknown LINBO command: {linbo_command}")

    command = _build_cmd()
    return execute_command(host, command, port=params.get("port"))


def get_linbo_status(host: str, port: int | None = None) -> dict:
    """Get LINBO status from a host (images, cache, disks).

    Returns:
        {success, images, cache, disks} or {success: False, error}
    """
    try:
        results = execute_commands(host, [
            "linbo_cmd listimages",
            "df -h /cache",
            "lsblk -J",
        ], port=port, continue_on_error=True)

        return {
            "success": True,
            "images": results[0]["stdout"].strip().split("\n") if results[0]["success"] else [],
            "cache": results[1]["stdout"] if len(results) > 1 and results[1]["success"] else "",
            "disks": results[2]["stdout"] if len(results) > 2 and results[2]["success"] else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def reset_key_cache() -> None:
    """Reset the cached SSH key (for testing)."""
    global _cached_key
    _cached_key = None
