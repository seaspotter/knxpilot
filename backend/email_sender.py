"""
Sends KNXpilot PDF exports (Pflichtenheft, Funktionscheckliste, Übergabe-
Checkliste, Dokumentation) to the customer/other stakeholders by email -
see routers/email.py for the endpoint and per-document PDF-building call
sites. Deliberately a manual, one-click-per-send action (never triggered
automatically, e.g. right after a signature is captured) - the send
dialog always shows exactly who's about to receive what before anything
goes out.

Uses only the standard library (smtplib + email.message.EmailMessage) -
same "no new dependency for a handful of network calls" choice as
backup.py's Nextcloud WebDAV client.
"""
import smtplib
import ssl
from email.message import EmailMessage


class EmailConfigError(Exception):
    """SMTP isn't configured, or a required field is missing - distinct
    from EmailSendError so routers/email.py can return a clearer "not set
    up yet" message pointing at Setup -> E-Mail instead of a raw SMTP
    error."""


class EmailSendError(Exception):
    """SMTP is configured but the actual send failed (wrong credentials,
    unreachable host, rejected recipient, timeout, ...) - wraps the
    underlying smtplib/socket exception's message."""


def _smtp_connect(company):
    host = (company.get("smtp_host") or "").strip()
    if not host:
        raise EmailConfigError("SMTP-Server fehlt (Setup → E-Mail).")
    port = company.get("smtp_port") or 587
    encryption = company.get("smtp_encryption") or "starttls"
    try:
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            if encryption == "starttls":
                server.starttls(context=ssl.create_default_context())
        username = (company.get("smtp_username") or "").strip()
        if username:
            server.login(username, company.get("smtp_password") or "")
        return server
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(str(e)) from e


def _build_message(company, to_addrs, cc_addrs, subject, body_text):
    from_email = (company.get("smtp_from_email") or "").strip()
    if not from_email:
        raise EmailConfigError("Absenderadresse fehlt (Setup → E-Mail).")
    if not to_addrs and not cc_addrs:
        raise EmailConfigError("Keine Empfänger angegeben.")

    msg = EmailMessage()
    from_name = (company.get("name") or "").strip()
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    if to_addrs:
        msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    msg["Subject"] = subject
    msg.set_content(body_text)
    return msg, from_email


def send_pdf_email(company, to_addrs, cc_addrs, subject, body_text, pdf_bytes, pdf_filename):
    """Sends one PDF as an attachment. to_addrs/cc_addrs are lists of
    already-trimmed, non-empty email address strings (see
    routers/email.py's recipient parsing/validation) - at least one of the
    two must be non-empty."""
    if not company.get("smtp_enabled"):
        raise EmailConfigError("Der E-Mail-Versand ist nicht aktiviert (Setup → E-Mail).")

    msg, from_email = _build_message(company, to_addrs, cc_addrs, subject, body_text)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    try:
        with _smtp_connect(company) as server:
            server.send_message(msg, from_addr=from_email, to_addrs=to_addrs + cc_addrs)
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(str(e)) from e


def send_test_email(company, to_addr):
    """Setup -> E-Mail's "Test-E-Mail senden" button - confirms the SMTP
    settings actually work before relying on them for a real send."""
    if not company.get("smtp_enabled"):
        raise EmailConfigError("Der E-Mail-Versand ist nicht aktiviert (Setup → E-Mail).")

    msg, from_email = _build_message(
        company, [to_addr], [],
        "KNXpilot – Test-E-Mail",
        "Diese Test-E-Mail bestätigt, dass die SMTP-Einstellungen in KNXpilot funktionieren.",
    )
    try:
        with _smtp_connect(company) as server:
            server.send_message(msg, from_addr=from_email, to_addrs=[to_addr])
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(str(e)) from e
