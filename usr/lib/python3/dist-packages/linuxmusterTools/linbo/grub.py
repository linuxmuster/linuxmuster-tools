"""
LINBO GRUB Config Reader — reads existing GRUB config files from disk.

Does NOT generate GRUB configs — that is done by the linbo-api locally.
This module only reads what linuxmuster-import-devices or linbo-api has written.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from ..common.timestamps import get_utc_mtime


logger = logging.getLogger(__name__)

GRUB_DIR_DEFAULT = '/srv/linbo/boot/grub'


class LinboGrubReader:
    """Read-only access to GRUB config files."""

    def __init__(self, grub_dir: str = GRUB_DIR_DEFAULT):
        self.grub_dir = Path(grub_dir)

    def list_grub_cfg_ids(self) -> list[str]:
        """Return sorted list of GRUB config group IDs (stems of *.cfg files)."""
        ids = []
        for p in sorted(self.grub_dir.glob("*.cfg")):
            group = p.stem
            if group:
                ids.append(group)
        return ids

    def get_configs_by_ids(self, ids: list[str]) -> list[dict]:
        """Return GRUB config content and mtime for given group IDs.

        Returns list of {id, content, updatedAt} dicts.
        Skips IDs whose .cfg file does not exist.
        """
        results = []
        for group_id in ids:
            cfg_path = self.grub_dir / f"{group_id}.cfg"
            if not cfg_path.is_file():
                continue
            try:
                content = cfg_path.read_text(encoding="utf-8")
            except OSError:
                continue

            mtime = get_utc_mtime(cfg_path)
            results.append({
                "id": group_id,
                "content": content,
                "updatedAt": mtime.isoformat() if mtime else None,
            })

        return results

    def get_all_grub_configs(self, school_groups: set[str] | None = None) -> list[dict]:
        """Return all GRUB configs, optionally filtered by school groups.

        Always includes main grub.cfg. Group configs are filtered by
        school_groups if provided.

        Returns list of {id, filename, content, updatedAt} dicts.
        """
        configs = []

        # Always include main grub.cfg
        main_cfg = self.grub_dir / "grub.cfg"
        if main_cfg.is_file():
            try:
                content = main_cfg.read_text(encoding="utf-8")
                mtime = get_utc_mtime(main_cfg)
                configs.append({
                    "id": "grub",
                    "filename": "grub.cfg",
                    "content": content,
                    "updatedAt": mtime.isoformat() if mtime else None,
                })
            except OSError as exc:
                logger.warning("Failed to read grub.cfg: %s", exc)

        # Group configs
        for p in sorted(self.grub_dir.glob("*.cfg")):
            if p.name == "grub.cfg":
                continue
            group = p.stem
            if school_groups is not None and group not in school_groups:
                continue
            try:
                content = p.read_text(encoding="utf-8")
                mtime = get_utc_mtime(p)
                configs.append({
                    "id": group,
                    "filename": f"{group}.cfg",
                    "content": content,
                    "updatedAt": mtime.isoformat() if mtime else None,
                })
            except OSError:
                continue

        return configs

    def get_cfg_mtime(self, group_id: str) -> datetime | None:
        """Return mtime for a specific GRUB config file."""
        cfg_path = self.grub_dir / f"{group_id}.cfg"
        return get_utc_mtime(cfg_path)
