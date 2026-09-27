"""Small shared helpers with no dependencies on the rest of the app."""
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import quote

# An open Klärung older than this counts as "aged" - used both by
# klaerungsliste.py (per-entry age_days/aged flag) and projects.py (the
# all-projects dashboard's aged-count rollup), so the two stay consistent.
AGED_KLAERUNG_DAYS = 7


def join_parts(*parts):
    """Join name fragments with a single space, skipping empty ones (avoids double spaces)."""
    return " ".join(p for p in parts if p)


def human_file_size(size):
    """"184.0 KB" - shared by every file listing rendered server-side
    (Setup -> Backup's file list, the overview tab's Dateien list). "" for
    a missing/zero size (backup listings don't always know it)."""
    if not size:
        return ""
    for exponent, unit in ((3, "GB"), (2, "MB"), (1, "KB")):
        if size >= 1024 ** exponent:
            return f"{size / 1024 ** exponent:.1f} {unit}"
    return f"{size} B"


def channel_letters(n):
    """Spreadsheet-style channel labels: A, B, ..., Z, AA, AB, ... for n channels."""
    result = []
    for i in range(1, n + 1):
        label = ""
        x = i
        while x > 0:
            x, rem = divmod(x - 1, 26)
            label = chr(65 + rem) + label
        result.append(label)
    return result


def content_disposition(filename, disposition="attachment"):
    """Content-Disposition header value that survives any filename. HTTP
    headers are Latin-1 only, so a project name like "Haus – Süd" (en dash)
    used to crash the download with a 500, and a quote broke the header.
    Sends an ASCII fallback (umlauts transliterated, anything else -> "_")
    plus the exact UTF-8 name per RFC 5987, which every current browser uses."""
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r'[^A-Za-z0-9 ._()-]', "_", ascii_name).strip() or "download"
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def local_time_text(value):
    """"26.09.2026 14:32" in the server's local time for a stored timestamp -
    either sqlite's CURRENT_TIMESTAMP ("2026-09-26 12:32:05", UTC) or an
    ISO string with offset (signatures). "" for empty/unparseable values."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")
