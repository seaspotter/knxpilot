"""Labels tab rendered server-side (htmx): the plain form via
backend/routers/labels.py's /hx/... endpoint. The label-sheet PDF export
itself is covered by tests/test_exports.py (export-labels.pdf)."""
from conftest import ok


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_format_options(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    body = html(client.get(f"/hx/projects/{pid}/labels"))
    assert "Avery Zweckform L6037" in body
    assert 'data-size="189"' in body
    assert 'id="label-format"' in body and 'id="label-source"' in body
