"""
Server-rendered HTML fragments for tabs that use htmx (vendored in
frontend/vendor/, see DEVELOPMENT.md "htmx tabs"). Templates live in
backend/templates/<tab>/; Jinja's autoescaping is on for .html, so user
text (room names, Klärungen, ...) is escaped by default - unlike the
template-literal .innerHTML rendering of the classic JS tabs.
"""
from datetime import timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def client_zone(request):
    """The browser's time zone, sent by ui.js on every htmx request
    (X-Timezone = IANA name, DST-correct; X-Timezone-Offset = the current
    offset in minutes as a fallback if the name is unknown here). The
    server itself usually runs on UTC inside the container."""
    name = request.headers.get("X-Timezone", "")
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    try:
        offset = int(request.headers.get("X-Timezone-Offset", "0"))
    except ValueError:
        offset = 0
    return timezone(timedelta(minutes=-offset))
