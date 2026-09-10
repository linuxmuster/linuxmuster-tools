import locale
import time
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


def linbo_timestamp_to_epoch(timestamp):
    """
    Convert a LINBO timestamp (YYYYMMDDHHMI) to a Unix epoch.

    LINBO clients write their own wall clock, which matches the server's local
    time: verified by comparing the content of *_image.status files with the
    mtime of those same files, written by the server on reception, at two
    different UTC offsets (CET and CEST). The timestamp is therefore read as
    server-local time, not as UTC.

    :param timestamp: Timestamp as written by LINBO, e.g. 202608071440
    :type timestamp: string
    :return: Seconds since the epoch
    :rtype: float
    """


    ## Linbo locale is en_GB, not necessarily the server locale
    saved = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    try:
        parsed = datetime.strptime(timestamp, '%Y%m%d%H%M')
    finally:
        # A malformed timestamp raises: without this the whole process would
        # be left in C.UTF-8.
        locale.setlocale(locale.LC_ALL, saved)

    return time.mktime(parsed.timetuple())
