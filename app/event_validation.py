import re
from datetime import date
from typing import Optional

# Exact YYYY-MM-DD only. date.fromisoformat() alone is too permissive (it also
# accepts compact "YYYYMMDD" and ISO week-date forms in newer Python versions),
# and SQLite's own date() function does not understand those - a value that
# passes fromisoformat() but not this regex would parse fine in Python yet
# silently fail every SQL date() comparison, making the event invisible.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_iso_date(value: Optional[str]) -> bool:
    """None is valid (no date set). Anything else must be exact YYYY-MM-DD
    and a real calendar date."""
    if value is None:
        return True

    if not _DATE_RE.match(value):
        return False

    try:
        date.fromisoformat(value)
    except ValueError:
        return False

    return True
