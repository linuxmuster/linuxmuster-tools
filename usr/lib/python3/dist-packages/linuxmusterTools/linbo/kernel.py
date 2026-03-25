"""
LINBO Kernel Management — variant switching and rebuild control.

Supports stable, longterm, and legacy kernel variants.
Persists state via JSON file, uses file-based locking for rebuilds.
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/linuxmuster/linbo")
LINBO_DIR = os.environ.get("LINBO_DIR", "/srv/linbo")

VALID_VARIANTS = ["stable", "longterm", "legacy"]
CUSTOM_KERNEL_FILE = Path(CONFIG_DIR) / "custom_kernel"
KERNEL_STATE_FILE = Path(CONFIG_DIR) / "kernel_state.json"
REBUILD_LOCK = Path(CONFIG_DIR) / ".rebuild.lock"

DEFAULT_STATE = {
    "lastSwitchAt": None,
    "lastError": None,
    "lastRequestedVariant": None,
    "lastSuccessfulVariant": None,
    "rebuildStatus": "completed",
}


class LinboKernelManager:
    """Manage kernel variant switching and rebuild state."""

    def __init__(self):
        self._rebuild_active = False

    def read_state(self) -> dict:
        """Read kernel state from JSON file.

        Detects interrupted rebuilds (crash recovery).
        """
        try:
            raw = KERNEL_STATE_FILE.read_text(encoding="utf-8")
            state = {**DEFAULT_STATE, **json.loads(raw)}

            if state["rebuildStatus"] == "running" and not self._rebuild_active:
                state["rebuildStatus"] = "failed"
                state["lastError"] = "Rebuild interrupted (process restart)"
                self.write_state(state)

            return state
        except FileNotFoundError:
            return {**DEFAULT_STATE}
        except json.JSONDecodeError:
            logger.error("Corrupt kernel_state.json, resetting")
            return {**DEFAULT_STATE}

    def write_state(self, updates: dict) -> dict:
        """Write kernel state atomically (temp + rename)."""
        try:
            raw = KERNEL_STATE_FILE.read_text(encoding="utf-8")
            state = {**DEFAULT_STATE, **json.loads(raw), **updates}
        except (FileNotFoundError, json.JSONDecodeError):
            state = {**DEFAULT_STATE, **updates}

        fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            os.rename(tmp, str(KERNEL_STATE_FILE))
        except Exception:
            os.unlink(tmp)
            raise

        return state

    def read_custom_kernel_config(self) -> dict:
        """Read custom_kernel config file.

        Returns:
            {variant, raw, valid, warning}
        """
        try:
            raw = CUSTOM_KERNEL_FILE.read_text(encoding="utf-8")
            lines = [l for l in raw.splitlines()
                     if l.strip() and not l.strip().startswith("#")]
            kernel_lines = [l for l in lines if "KERNELPATH=" in l]

            if not kernel_lines:
                return {"variant": "stable", "raw": raw, "valid": True, "warning": None}

            last = kernel_lines[-1]
            value = last.split("=", 1)[1].strip().strip('"').strip()

            if value in VALID_VARIANTS:
                return {"variant": value, "raw": raw, "valid": True, "warning": None}
            if value == "":
                return {"variant": "stable", "raw": raw, "valid": True, "warning": None}

            return {
                "variant": value,
                "raw": raw,
                "valid": False,
                "warning": f"Unknown variant: {value}",
            }
        except FileNotFoundError:
            return {"variant": "stable", "raw": "", "valid": True, "warning": None}

    def write_custom_kernel_config(self, variant: str) -> None:
        """Write custom_kernel config file.

        Args:
            variant: Kernel variant (stable, longterm, legacy)

        Raises:
            ValueError: If variant is not valid
        """
        if variant not in VALID_VARIANTS:
            raise ValueError(f"Invalid variant: {variant}. Must be one of {VALID_VARIANTS}")

        content = f'KERNELPATH="{variant}"\n'
        CUSTOM_KERNEL_FILE.write_text(content, encoding="utf-8")

    def get_status(self) -> dict:
        """Get combined kernel status.

        Returns:
            {state, customKernel, variants}
        """
        state = self.read_state()
        config = self.read_custom_kernel_config()

        # List available variants from filesystem
        variants = []
        for v in VALID_VARIANTS:
            kernel_path = Path(LINBO_DIR) / v / "linbo64"
            variants.append({
                "name": v,
                "available": kernel_path.is_file(),
                "active": config["variant"] == v,
            })

        return {
            "state": state,
            "customKernel": config,
            "variants": variants,
        }

    def switch_variant(self, variant: str, rebuild: bool = True) -> dict:
        """Switch kernel variant and optionally trigger linbofs rebuild.

        Args:
            variant: Target variant
            rebuild: Whether to trigger linbofs rebuild

        Returns:
            {success, state, rebuild}
        """
        if variant not in VALID_VARIANTS:
            raise ValueError(f"Invalid variant: {variant}")

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        self.write_custom_kernel_config(variant)
        state = self.write_state({
            "lastSwitchAt": now,
            "lastRequestedVariant": variant,
            "rebuildStatus": "pending" if rebuild else "completed",
        })

        rebuild_result = None
        if rebuild:
            rebuild_result = self.trigger_rebuild(variant)

        return {"success": True, "state": state, "rebuild": rebuild_result}

    def trigger_rebuild(self, variant: str) -> dict:
        """Trigger linbofs64 rebuild via update-linbofs.

        Runs sudo /usr/sbin/update-linbofs with a 5-minute timeout.
        Tracks state as running → completed/failed.

        Args:
            variant: The kernel variant being built (for state tracking)

        Returns:
            {success, output} on success, {success, error} on failure
        """
        from datetime import datetime, timezone

        script_path = os.environ.get("UPDATE_LINBOFS_SCRIPT", "/usr/sbin/update-linbofs")

        # Acquire file-based lock
        lock_fd = None
        try:
            lock_fd = os.open(str(REBUILD_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return {"success": False, "error": "Rebuild already in progress (lock exists)"}

        self._rebuild_active = True
        self.write_state({"rebuildStatus": "running"})

        try:
            env = {
                **os.environ,
                "LINBO_DIR": LINBO_DIR,
                "CONFIG_DIR": CONFIG_DIR,
            }

            result = subprocess.run(
                ["sudo", script_path],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )

            self._rebuild_active = False
            output = result.stdout + result.stderr

            if result.returncode == 0:
                self.write_state({
                    "rebuildStatus": "completed",
                    "lastSuccessfulVariant": variant,
                    "lastError": None,
                })
                return {"success": True, "output": output}
            else:
                error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                self.write_state({
                    "rebuildStatus": "failed",
                    "lastError": error_msg,
                })
                return {"success": False, "error": error_msg, "output": output}

        except subprocess.TimeoutExpired:
            self._rebuild_active = False
            self.write_state({
                "rebuildStatus": "failed",
                "lastError": "Rebuild timed out after 300s",
            })
            return {"success": False, "error": "Rebuild timed out after 300s"}

        except Exception as e:
            self._rebuild_active = False
            self.write_state({
                "rebuildStatus": "failed",
                "lastError": str(e),
            })
            return {"success": False, "error": str(e)}

        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            try:
                os.unlink(str(REBUILD_LOCK))
            except OSError:
                pass
