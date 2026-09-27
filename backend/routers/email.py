"""
Send-by-email tab plumbing: a manual "Per E-Mail senden" action next to
each PDF export's existing "PDF herunterladen" button (Pflichtenheft,
Funktionscheckliste, Übergabe-Checkliste, Dokumentation, Klärungsliste's
"Offene Punkte") - never triggered
automatically (e.g. right after a signature is captured), so the sender
always sees and confirms exactly who's about to receive what.

Reuses each document's existing PDF-building function (factored out
alongside its download endpoint - see build_specification_pdf_bytes() in
specification.py, build_function_checklist_pdf_bytes()/
build_handover_checklist_pdf_bytes() in checklists.py,
build_documentation_pdf_bytes() in documentation.py) so the emailed PDF is
always byte-for-byte the same document you'd get from the download button.

The actual SMTP mechanics live in ../email_sender.py.
"""
import re

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..email_sender import EmailConfigError, EmailSendError, send_pdf_email, send_test_email
from ..models import SendEmailIn, TestEmailIn
from .specification import build_specification_pdf_bytes
from .checklists import build_function_checklist_pdf_bytes, build_handover_checklist_pdf_bytes
from .documentation import build_documentation_pdf_bytes
from .clarification_list import build_clarification_list_pdf_bytes

router = APIRouter(tags=["email"])

# (pdf-bytes builder, document title used in the subject line, a short
# German noun phrase for "im Anhang finden Sie ___" in the body text).
DOCUMENT_BUILDERS = {
    "specification": (build_specification_pdf_bytes, "Pflichtenheft", "das Pflichtenheft"),
    "function_checklist": (build_function_checklist_pdf_bytes, "Funktionscheckliste", "die Funktionscheckliste"),
    "handover_checklist": (build_handover_checklist_pdf_bytes, "Übergabe-Checkliste", "die Übergabe-Checkliste"),
    "documentation": (build_documentation_pdf_bytes, "Dokumentation", "die vollständige Projektdokumentation"),
    "clarification_list": (build_clarification_list_pdf_bytes, "Offene Punkte", "die offenen Punkte zur Klärung"),
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_recipients(raw: str):
    """Splits a free-text "a@b.de, c@d.de; e@f.de" field into a clean list -
    tolerates commas, semicolons and stray whitespace, since that's exactly
    how the additional-recipients field (and the send dialog) are typed."""
    parts = re.split(r"[,;]", raw or "")
    return [p.strip() for p in parts if p.strip()]


def _valid_email(addr: str) -> bool:
    return bool(_EMAIL_RE.match(addr))


@router.get("/api/projects/{project_id}/email-defaults")
def get_email_defaults(project_id: int):
    """Pre-fill data for the send dialog - project's stored recipient(s)
    plus whether SMTP is configured at all and whether "Kopie an mich"
    should start checked."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
    return {
        "smtp_enabled": bool(company["smtp_enabled"]),
        "to": project["email"] or "",
        "additional_recipients": project["additional_recipients"] or "",
        "cc_self_default": bool(company["smtp_cc_self_default"]),
        "company_email": company["email"] or "",
    }


@router.post("/api/projects/{project_id}/send-email")
def send_project_email(project_id: int, body: SendEmailIn):
    if body.document not in DOCUMENT_BUILDERS:
        raise HTTPException(400, "Unbekannter Dokumenttyp")
    build_fn, doc_title, body_intro = DOCUMENT_BUILDERS[body.document]

    to_addrs = _parse_recipients(body.to)
    cc_addrs = _parse_recipients(body.cc)
    if not to_addrs and not cc_addrs:
        raise HTTPException(400, "Mindestens ein Empfänger ist erforderlich.")
    invalid = [a for a in to_addrs + cc_addrs if not _valid_email(a)]
    if invalid:
        raise HTTPException(400, f"Ungültige E-Mail-Adresse(n): {', '.join(invalid)}")

    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())

    pdf_bytes, filename = build_fn(project_id)

    subject = f"{doc_title} — {project['name']}"
    body_lines = [
        "Guten Tag",
        "",
        f'im Anhang finden Sie {body_intro} zum Projekt "{project["name"]}".',
    ]
    if body.note.strip():
        body_lines += ["", body.note.strip()]
    body_lines += ["", "Freundliche Grüsse", company.get("name") or ""]

    try:
        send_pdf_email(company, to_addrs, cc_addrs, subject, "\n".join(body_lines), pdf_bytes, filename)
    except EmailConfigError as e:
        raise HTTPException(400, str(e))
    except EmailSendError as e:
        raise HTTPException(502, f"E-Mail-Versand fehlgeschlagen: {e}")

    return {"ok": True, "to": to_addrs, "cc": cc_addrs}


@router.post("/api/send-test-email")
def send_test_email_endpoint(body: TestEmailIn):
    to_addr = body.to.strip()
    if not _valid_email(to_addr):
        raise HTTPException(400, "Ungültige E-Mail-Adresse.")
    with get_db() as db:
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
    try:
        send_test_email(company, to_addr)
    except EmailConfigError as e:
        raise HTTPException(400, str(e))
    except EmailSendError as e:
        raise HTTPException(502, f"Test-E-Mail fehlgeschlagen: {e}")
    return {"ok": True}
