from datetime import datetime, timezone
from pathlib import Path


def get_utc_mtime(path: Path) -> datetime | None:
    """
    Return file mtime as UTC datetime, or None if missing.
    """


    if not path.exists():
        return None

    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None