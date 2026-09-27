"""The specification ("Pflichtenheft") and documentation ("Dokumentation")
tabs rendered server-side (htmx): the tab body is the same "Inhalt" list the
JSON *-contents endpoints already produced, now server-rendered."""
from conftest import ok, seed_musterhaus


def test_specification_tab_matches_contents_endpoint(client):
    pid = seed_musterhaus(client)
    sections = ok(client.get(f"/api/projects/{pid}/specification-contents"))
    body = client.get(f"/hx/projects/{pid}/specification").text
    assert 'onclick="downloadSpecification()"' in body and 'onclick="previewSpecification()"' in body
    for i, s in enumerate(sections, start=1):
        assert s["title"] in body
        if s["included"]:
            assert f"{i}. {s['title']}" in body
        assert s["detail"] in body


def test_documentation_tab_matches_contents_endpoint(client):
    pid = seed_musterhaus(client)
    sections = ok(client.get(f"/api/projects/{pid}/documentation-contents"))
    body = client.get(f"/hx/projects/{pid}/documentation").text
    assert 'onclick="downloadDocumentation()"' in body and 'onclick="previewDocumentation()"' in body
    for s in sections:
        assert s["title"] in body
        assert s["detail"] in body
    # a warn-flagged row (e.g. Funktionscheckliste with 0 tested) shows the "warn" class
    warn_titles = [s["title"] for s in sections if s["warn"]]
    if warn_titles:
        assert 'class="doc-detail warn"' in body
