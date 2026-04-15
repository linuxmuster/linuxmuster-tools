"""
LINBO Terminal Service — interactive SSH session management.

Manages SSH sessions with PTY support for web-based terminal access
to LINBO clients. Supports session lifecycle, input/output streaming,
PTY resize, and idle timeout enforcement.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from linuxmusterTools.common.checks import NameChecker


name_checker = NameChecker()
logger = logging.getLogger(__name__)

MAX_SESSIONS = int(os.environ.get("TERMINAL_MAX_SESSIONS", "10"))
IDLE_TIMEOUT = int(os.environ.get("TERMINAL_IDLE_TIMEOUT", str(30 * 60)))  # 30 min


class TerminalSession:
    """A single interactive SSH terminal session."""

    def __init__(self, session_id: str, host_ip: str, user_id: str):
        self.id = session_id
        self.host_ip = host_ip
        self.user_id = user_id
        self.mode = "pty"
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self._client = None
        self._channel = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hostIp": self.host_ip,
            "userId": self.user_id,
            "mode": self.mode,
            "createdAt": self.created_at.isoformat(),
            "lastActivity": self.last_activity.isoformat(),
        }

    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    def is_idle(self) -> bool:
        """Check if session has exceeded idle timeout."""
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > IDLE_TIMEOUT


class LinboTerminalManager:
    """Manage interactive SSH terminal sessions."""

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}

    def list_sessions(self) -> list[dict]:
        """List all active sessions."""
        self._cleanup_idle()
        return [s.to_dict() for s in self._sessions.values()]

    def get_session(self, session_id: str) -> TerminalSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def create_session(self, host_ip: str, user_id: str) -> TerminalSession:
        """Create a new terminal session.

        Args:
            host_ip: Target LINBO client IP (must be valid IPv4)
            user_id: ID of the user creating the session

        Returns:
            New TerminalSession

        Raises:
            ValueError: If host_ip is not a valid IPv4 address
            RuntimeError: If max sessions reached
        """
        if not host_ip or not name_checker.check_ip(host_ip):
            raise ValueError(f"Invalid IP address: {host_ip}")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")

        self._cleanup_idle()

        if len(self._sessions) >= MAX_SESSIONS:
            raise RuntimeError(f"Maximum sessions ({MAX_SESSIONS}) reached")

        session_id = str(uuid.uuid4())
        session = TerminalSession(session_id, host_ip, user_id)
        self._sessions[session_id] = session

        logger.info("Terminal session %s created for %s by %s", session_id, host_ip, user_id)
        return session

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a terminal session.

        Returns:
            True if session was found and destroyed
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False

        logger.info("Terminal session %s destroyed", session_id)
        return True

    def destroy_all(self) -> int:
        """Destroy all sessions. Returns count."""
        count = len(self._sessions)
        self._sessions.clear()
        return count

    def _cleanup_idle(self):
        """Remove sessions that have exceeded idle timeout."""
        idle = [sid for sid, s in self._sessions.items() if s.is_idle()]
        for sid in idle:
            logger.info("Terminal session %s idle timeout", sid)
            self._sessions.pop(sid, None)
