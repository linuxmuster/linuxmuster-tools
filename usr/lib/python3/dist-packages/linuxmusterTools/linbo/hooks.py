"""
LINBO Hook Management — discover and inspect update-linbofs hooks.

Scans pre/post hook directories and reads build manifest for execution history.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_HOOKS_DIR = "/etc/linuxmuster/linbo/hooks"
MANIFEST_PATH = "/srv/linbo/linbofs-build-manifest.json"


class LinboHookManager:
    """Read-only access to update-linbofs hooks."""

    def __init__(self, hooks_dir: str = DEFAULT_HOOKS_DIR):
        self.hooks_dir = Path(hooks_dir)
        self.pre_dir = self.hooks_dir / "update-linbofs.pre.d"
        self.post_dir = self.hooks_dir / "update-linbofs.post.d"

    def get_hooks(self) -> list[dict]:
        """List all pre/post hooks with metadata.

        Returns:
            List of {name, type, path, executable, size} dicts
        """
        hooks = []
        manifest = self._read_manifest()

        for hook_type, hook_dir in [("pre", self.pre_dir), ("post", self.post_dir)]:
            if not hook_dir.is_dir():
                continue
            for f in sorted(hook_dir.iterdir()):
                if not f.is_file():
                    continue
                stat = f.stat()
                hook = {
                    "name": f.name,
                    "type": hook_type,
                    "path": str(f),
                    "executable": os.access(f, os.X_OK),
                    "size": stat.st_size,
                }
                # Merge manifest data if available
                hook_key = f"{hook_type}/{f.name}"
                if hook_key in manifest:
                    hook["lastExitCode"] = manifest[hook_key].get("exitCode")
                    hook["lastRunAt"] = manifest[hook_key].get("runAt")

                hooks.append(hook)

        return hooks

    def _read_manifest(self) -> dict:
        """Read build manifest for hook execution history."""
        try:
            text = Path(MANIFEST_PATH).read_text(encoding="utf-8")
            data = json.loads(text)
            return data.get("hooks", {})
        except (OSError, json.JSONDecodeError):
            return {}
