"""Manual downloads against a local HTTP server: real PDFs are stored,
web pages and truncated downloads are rejected with a readable error."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend.routers.manuals import _fetch_manual_bytes


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/ok.pdf":
            body = b"%PDF-1.4\n" + b"x" * 500
            self._send(body, "application/pdf", len(body))
        elif self.path == "/page.pdf":
            body = b"<html><script>alert(1)</script></html>"
            self._send(body, "text/html", len(body))
        elif self.path == "/drop.pdf":
            self._send(b"%PDF-1.4 partial", "application/pdf", 100000)

    def _send(self, body, ctype, length):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_real_pdf_is_accepted(server):
    data, ctype = _fetch_manual_bytes(f"{server}/ok.pdf")
    assert data.startswith(b"%PDF") and ctype == "application/pdf"


@pytest.mark.parametrize("path,message", [("/page.pdf", "Kein PDF"), ("/drop.pdf", "unvollständig")])
def test_bad_downloads_are_rejected(server, path, message):
    with pytest.raises(ValueError, match=message):
        _fetch_manual_bytes(f"{server}{path}")


def test_non_http_scheme_rejected():
    with pytest.raises(ValueError, match="http"):
        _fetch_manual_bytes("file:///etc/passwd")
