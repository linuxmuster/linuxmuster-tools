"""Production-oriented profile core for LINBO Windows drivers.

This module deliberately contains no HTTP, archive extraction, inventory
parsing or postsync rendering logic. It is the public facade consumed by
``linuxmuster-api`` and future CLI/WebUI integrations; the specialized
implementations remain isolated in sibling modules.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Sequence

from .driver_hooks import LinboDriverHookManager, validate_image_name
from .driver_inventory import DEFAULT_SCHOOL, list_server_hardware, validate_school_name
from .driver_matching import (
    MAX_MATCH_CONF_BYTES,
    MatchConfigError,
    build_match_rule,
    parse_match_conf,
    serialize_match_conf,
)
from .driver_storage import (
    atomic_write_text,
    delete_profile_directory,
    iter_profile_directories,
    list_regular_files,
    mutation_lock,
    profile_path,
    read_text_limited,
    require_profile_directory,
    require_regular_file,
    validate_profile_name,
)


__all__ = [
    "DriverInventoryNotFoundError",
    "DriverProfileConflictError",
    "DriverProfileExistsError",
    "DriverProfileAssignedError",
    "LinboDriverManager",
]


logger = logging.getLogger(__name__)

LINBO_DIR = Path(os.environ.get("LINBO_DIR", "/srv/linbo"))
DEFAULT_DRIVERS_BASE = Path(
    os.environ.get("DRIVERS_BASE", str(LINBO_DIR / "drivers"))
)
DEFAULT_IMAGES_BASE = Path(
    os.environ.get("IMAGE_DIR", str(LINBO_DIR / "images"))
)
MATCH_CONF_FILENAME = "match.conf"
IMAGE_CONF_FILENAME = "image.conf"
_DEFAULT_DEVICES_CSV_SETTING = object()


class DriverInventoryNotFoundError(FileNotFoundError):
    """Raised when a host has no LINBO inventory in the selected school."""

    def __init__(self, school: str, hostname: str) -> None:
        super().__init__(f"hardware inventory not found: {school}/{hostname}")
        self.school = school
        self.hostname = hostname


class DriverProfileConflictError(FileExistsError):
    """Base class for expected, administrator-resolvable profile conflicts."""


class DriverProfileExistsError(DriverProfileConflictError):
    """Raised when creating a profile would replace an existing path."""

    def __init__(self, profile: str) -> None:
        super().__init__(f"driver profile already exists: {profile}")
        self.profile = profile


class DriverProfileAssignedError(DriverProfileConflictError):
    """Raised when deleting a profile would orphan its published image hook."""

    def __init__(self, profile: str, image: str) -> None:
        super().__init__(
            f"driver profile {profile!r} is assigned to image {image!r}; "
            "remove the image assignment before deleting the profile"
        )
        self.profile = profile
        self.image = image


class LinboDriverManager:
    """Manage filesystem-backed LINBO driver profiles."""

    def __init__(
        self,
        drivers_base: str | Path | None = None,
        *,
        images_base: str | Path | None = None,
        hwinfo_dir: str | Path | None = None,
        devices_csv: str | Path | None | object = _DEFAULT_DEVICES_CSV_SETTING,
        stale_hours: float | str | None = None,
    ):
        self.base = Path(drivers_base) if drivers_base is not None else DEFAULT_DRIVERS_BASE
        self.images_base = (
            Path(images_base) if images_base is not None else DEFAULT_IMAGES_BASE
        )
        self.hook_manager = LinboDriverHookManager(
            drivers_root=self.base,
            images_root=self.images_base,
            lock_path=self.base / ".driver-profiles.lock",
        )
        self.hwinfo_dir = Path(hwinfo_dir) if hwinfo_dir is not None else None
        if devices_csv is _DEFAULT_DEVICES_CSV_SETTING:
            self.devices_csv = _DEFAULT_DEVICES_CSV_SETTING
        else:
            self.devices_csv = Path(devices_csv) if devices_csv is not None else None
        self.stale_hours = stale_hours

    def list_inventory(
        self,
        include_devices: bool = False,
        *,
        school: str = DEFAULT_SCHOOL,
    ) -> list[dict]:
        """Return server-side LINBO inventories using manager configuration."""

        if not isinstance(include_devices, bool):
            raise ValueError("include_devices must be a boolean")
        safe_school = validate_school_name(school)
        inventory_options = {
            "hwinfo_dir": self.hwinfo_dir,
            "school": safe_school,
            "stale_hours": self.stale_hours,
            "include_devices": include_devices,
        }
        # Omitting this keyword selects the native school-aware ``Devices``
        # provider. An explicit ``None`` disables metadata and filtering for
        # low-level diagnostics only.
        if self.devices_csv is not _DEFAULT_DEVICES_CSV_SETTING:
            inventory_options["devices_csv"] = self.devices_csv
        return list_server_hardware(
            **inventory_options,
        )

    def get_inventory(
        self,
        hostname: str,
        include_devices: bool = True,
        *,
        school: str = DEFAULT_SCHOOL,
    ) -> dict | None:
        """Find one school-scoped inventory by hostname, case-insensitively."""

        if not isinstance(hostname, str) or not hostname.strip():
            raise ValueError("hostname must not be empty")
        query = hostname.strip()
        inventories = self.list_inventory(
            include_devices=include_devices,
            school=school,
        )

        # Prefer exact global and school-local spellings; otherwise retain the
        # inventory module's deterministic sort order for case-folded matches.
        for key in ("hostname", "deviceHostname"):
            for inventory in inventories:
                if inventory.get(key) == query:
                    return inventory
        folded = query.casefold()
        for key in ("hostname", "deviceHostname"):
            for inventory in inventories:
                candidate = inventory.get(key)
                if isinstance(candidate, str) and candidate.casefold() == folded:
                    return inventory
        return None

    @staticmethod
    def suggest_profile_names(vendor: str, product: str) -> dict:
        """Return deterministic preferred and collision-fallback DMI slugs.

        The preferred name retains the existing readable naming scheme. The
        fallback includes the full SHA-256 of vendor and product separated by
        NUL, so two normalized readable slugs cannot silently select the same
        profile.
        """

        rule = build_match_rule(vendor, [product])
        normalized_vendor = rule.vendor
        normalized_product = rule.products[0]
        readable = re.sub(r"\s+", "_", f"{normalized_vendor}_{normalized_product}")
        readable = re.sub(r"[^a-zA-Z0-9._-]", "", readable)[:80]

        preferred = None
        try:
            preferred = validate_profile_name(readable)
        except ValueError:
            pass

        digest = hashlib.sha256(
            normalized_vendor.encode("utf-8")
            + b"\0"
            + normalized_product.encode("utf-8")
        ).hexdigest()
        stem = re.sub(r"^[^a-zA-Z0-9]+", "", readable) or "profile"
        stem = stem[:35].rstrip("._-") or "profile"
        fallback = validate_profile_name(f"{stem}-{digest}")
        return {"preferred": preferred, "fallback": fallback}

    def _inspect_dmi_candidate(
        self,
        name: str,
        vendor: str,
        product: str,
    ) -> tuple[str, dict | None]:
        try:
            profile = self.get_profile(name)
        except (FileNotFoundError, OSError, ValueError):
            return "occupied", None
        if profile is None:
            return "available", None

        match_conf = profile["matchConf"]
        if (
            match_conf.get("vendor") == vendor
            and product in match_conf.get("products", [])
        ):
            return "matching", profile
        return "occupied", profile

    def create_profile_from_inventory(
        self,
        hostname: str,
        name: str | None = None,
        *,
        school: str = DEFAULT_SCHOOL,
    ) -> dict:
        """Create a profile from a stored client inventory.

        Automatic naming is idempotent for the same DMI data.  A readable-name
        collision selects the deterministic hash fallback; an explicitly
        supplied name retains the strict ``create_profile`` semantics.
        """

        safe_school = validate_school_name(school)
        inventory = self.get_inventory(
            hostname,
            include_devices=False,
            school=safe_school,
        )
        if inventory is None:
            raise DriverInventoryNotFoundError(safe_school, hostname.strip())

        dmi = inventory.get("dmi")
        vendor = dmi.get("vendor") if isinstance(dmi, dict) else None
        product = dmi.get("product") if isinstance(dmi, dict) else None
        if not isinstance(vendor, str) or not vendor.strip():
            raise ValueError(f"hardware inventory for {hostname} has no DMI vendor")
        if not isinstance(product, str) or not product.strip():
            raise ValueError(f"hardware inventory for {hostname} has no DMI product")

        rule = build_match_rule(vendor, [product])
        vendor = rule.vendor
        product = rule.products[0]
        if name is not None:
            return self.create_profile(name, vendor, [product])

        suggestions = self.suggest_profile_names(vendor, product)
        preferred = suggestions["preferred"]
        fallback = suggestions["fallback"]

        preferred_state = "occupied"
        if preferred is not None:
            preferred_state, preferred_profile = self._inspect_dmi_candidate(
                preferred, vendor, product
            )
            if preferred_state == "matching" and preferred_profile is not None:
                return preferred_profile

        fallback_state, fallback_profile = self._inspect_dmi_candidate(
            fallback, vendor, product
        )
        if fallback_state == "matching" and fallback_profile is not None:
            return fallback_profile

        candidates = []
        if preferred is not None and preferred_state == "available":
            candidates.append(preferred)
        if fallback_state == "available":
            candidates.append(fallback)

        for candidate in candidates:
            try:
                return self.create_profile(candidate, vendor, [product])
            except DriverProfileExistsError:
                # Another API worker may have created the candidate after the
                # read above.  Accept it only if its match is exactly ours.
                state, profile = self._inspect_dmi_candidate(
                    candidate, vendor, product
                )
                if state == "matching" and profile is not None:
                    return profile

        raise DriverProfileConflictError(
            f"deterministic DMI profile names are occupied: {fallback}"
        )

    @staticmethod
    def _match_dict(content: str) -> dict:
        return parse_match_conf(content).as_dict()

    def _profile_summary(self, name: str) -> dict:
        profile = require_profile_directory(self.base, name)
        match_path = require_regular_file(profile / MATCH_CONF_FILENAME)
        content = read_text_limited(match_path, MAX_MATCH_CONF_BYTES)
        return {
            "name": profile.name,
            "path": str(profile),
            "hasMatchConf": True,
            "matchConf": self._match_dict(content),
            "image": self.get_profile_image(profile.name),
        }

    def list_available_images(self) -> list[dict[str, str]]:
        """Return complete native QCOW2 images usable for driver hooks."""

        return self.hook_manager.list_available_images()

    def get_profile_image(self, name: str) -> str | None:
        """Return the image assigned to a profile, if any."""

        return self.hook_manager.read_image_conf(name)

    def _ensure_canonical_match(self, name: str) -> None:
        """Migrate the current on-disk rule while holding the shared lock.

        The rule is deliberately re-read after acquiring the lock. This avoids
        overwriting a concurrent administrator update with values observed
        before that update.
        """

        with mutation_lock(self.base):
            profile = require_profile_directory(self.base, name)
            match_path = require_regular_file(profile / MATCH_CONF_FILENAME)
            rule = parse_match_conf(
                read_text_limited(match_path, MAX_MATCH_CONF_BYTES)
            )
            if rule.schema == "legacy":
                atomic_write_text(
                    match_path,
                    serialize_match_conf(rule.vendor, rule.products),
                    mode=0o644,
                )

    def set_profile_image(self, name: str, image: str) -> dict[str, str]:
        """Assign a profile to an image and transactionally publish hooks.

        Reading legacy WIP match aliases remains supported, but the client-side
        hook deliberately consumes only the canonical schema. Migrate such a
        profile before publishing so a successful assignment can actually
        match on LINBO clients.
        """

        safe_name = validate_profile_name(name)
        safe_image = validate_image_name(image)
        self._ensure_canonical_match(safe_name)

        return self.hook_manager.set_profile_image(safe_name, safe_image)

    def remove_profile_image(self, name: str) -> dict[str, str | None]:
        """Remove a profile assignment and publish the required tombstone."""

        return self.hook_manager.remove_profile_image(name)

    def reconcile_driver_hooks(self) -> dict[str, list]:
        """Rebuild every managed driver hook from persistent assignments."""

        return self.hook_manager.reconcile_all_postsync()

    def list_profiles(self) -> list[dict]:
        """List valid profiles, sorted by name.

        Invalid or incomplete directories are skipped and logged.  This is a
        fail-closed behavior: a malformed rule is never returned as deployable.
        """

        profiles = []
        for directory in iter_profile_directories(self.base):
            try:
                profiles.append(self._profile_summary(directory.name))
            except (FileNotFoundError, MatchConfigError, OSError, ValueError) as exc:
                logger.warning("Ignoring invalid driver profile %s: %s", directory.name, exc)
        return profiles

    def get_profile(self, name: str) -> dict | None:
        """Return a complete profile description, or ``None`` if absent.

        A present but malformed profile raises ``ValueError`` rather than being
        treated as usable.
        """

        safe_name = validate_profile_name(name)
        target = profile_path(self.base, safe_name)
        if not os.path.lexists(target):
            return None

        result = self._profile_summary(safe_name)
        files = list_regular_files(
            target,
            excluded_relative_paths=frozenset(
                {MATCH_CONF_FILENAME, IMAGE_CONF_FILENAME}
            ),
        )
        result["files"] = files
        result["totalSize"] = sum(item["size"] for item in files)
        return result

    def create_profile(
        self,
        name: str,
        vendor: str,
        products: Sequence[str] | None = None,
    ) -> dict:
        """Create a profile without ever overwriting an existing path."""

        safe_name = validate_profile_name(name)
        rule = build_match_rule(vendor, products)
        content = serialize_match_conf(rule.vendor, rule.products)

        with mutation_lock(self.base):
            target = profile_path(self.base, safe_name)
            if os.path.lexists(target):
                raise DriverProfileExistsError(safe_name)
            try:
                target.mkdir(mode=0o755)
            except FileExistsError as exc:
                # A non-cooperating writer can race the shared lock. Expose
                # the same stable domain error as the preflight check.
                raise DriverProfileExistsError(safe_name) from exc
            try:
                atomic_write_text(target / MATCH_CONF_FILENAME, content, mode=0o644)
            except Exception:
                try:
                    target.rmdir()
                except OSError:
                    pass
                raise

        profile = self.get_profile(safe_name)
        if profile is None:  # Defensive: creation above either succeeds or raises.
            raise RuntimeError(f"created driver profile disappeared: {safe_name}")
        return profile

    def update_match(
        self,
        name: str,
        vendor: str,
        products: Sequence[str] | None = None,
    ) -> dict:
        """Replace ``match.conf`` atomically using canonical key names.

        A legacy profile is migrated as part of a successful update.  The
        structured input is validated before any filesystem change occurs.
        """

        safe_name = validate_profile_name(name)
        rule = build_match_rule(vendor, products)
        content = serialize_match_conf(rule.vendor, rule.products)

        with mutation_lock(self.base):
            target = require_profile_directory(self.base, safe_name)
            require_regular_file(target / MATCH_CONF_FILENAME)
            atomic_write_text(target / MATCH_CONF_FILENAME, content, mode=0o644)

        profile = self.get_profile(safe_name)
        if profile is None:
            raise RuntimeError(f"updated driver profile disappeared: {safe_name}")
        return profile

    def delete_profile(self, name: str) -> bool:
        """Delete a valid managed profile and return whether it existed."""

        safe_name = validate_profile_name(name)
        with mutation_lock(self.base):
            target = profile_path(self.base, safe_name)
            if not os.path.lexists(target):
                return False

            # The valid match.conf is the ownership marker.  Never recursively
            # delete an arbitrary directory that only happens to share a name.
            match_path = require_regular_file(
                require_profile_directory(self.base, safe_name) / MATCH_CONF_FILENAME
            )
            parse_match_conf(read_text_limited(match_path, MAX_MATCH_CONF_BYTES))
            assigned_image = self.hook_manager.read_image_conf(safe_name)
            if assigned_image is not None:
                raise DriverProfileAssignedError(safe_name, assigned_image)
            delete_profile_directory(self.base, safe_name)
            return True
