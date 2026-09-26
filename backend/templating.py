"""
Server-rendered HTML fragments for tabs that use htmx (vendored in
frontend/vendor/, see DEVELOPMENT.md "htmx tabs"). Templates live in
backend/templates/<tab>/; Jinja's autoescaping is on for .html, so user
text (room names, Klärungen, ...) is escaped by default - unlike the
template-literal .innerHTML rendering of the classic JS tabs.
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
