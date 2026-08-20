"""
Shared PDF design system - used by every PDF export (Abgangsliste,
Geräteliste, Pflichtenheft) so they all look consistent: a dark banner
header, a light table style, and a footer with "Seite X von Y" + project
name on every page.
"""
import base64
import io

from fastapi.responses import StreamingResponse
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as pdfcanvas

PDF_BANNER_COLOR = colors.HexColor("#14532d")
PDF_ACCENT_COLOR = colors.HexColor("#16a34a")
PDF_MUTED_COLOR = colors.HexColor("#64748b")
PDF_BORDER_COLOR = colors.HexColor("#cbd5e1")
PDF_STRIPE_COLOR = colors.HexColor("#f1f5f9")


def pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("BannerTitle", fontName="Helvetica-Bold", fontSize=18, textColor=colors.white, leading=22))
    styles.add(ParagraphStyle("BannerSub", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#cbd5e1"), leading=14))
    styles.add(ParagraphStyle("SectionHeading", fontName="Helvetica-Bold", fontSize=13, textColor=PDF_BANNER_COLOR, spaceBefore=10, spaceAfter=4))
    styles.add(ParagraphStyle("RoomHeading", fontName="Helvetica-Bold", fontSize=11, textColor=PDF_ACCENT_COLOR, spaceBefore=6, spaceAfter=2))
    styles.add(ParagraphStyle("SubHeading", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.HexColor("#0f172a"), spaceBefore=4, spaceAfter=1, leading=13))
    styles.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#0f172a"), leading=13))
    styles.add(ParagraphStyle("BodyBullet", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#0f172a"), leading=13, leftIndent=4 * mm, spaceAfter=2))
    styles.add(ParagraphStyle("BodyMuted", fontName="Helvetica-Oblique", fontSize=9, textColor=PDF_MUTED_COLOR, leading=12))
    styles.add(ParagraphStyle("CompanyName", fontName="Helvetica-Bold", fontSize=13, textColor=PDF_BANNER_COLOR, leading=16))
    return styles


def pdf_title_banner(title, subtitle=""):
    """A full-width dark banner as the document header - used at the top of every PDF export."""
    styles = pdf_styles()
    content = [Paragraph(title, styles["BannerTitle"])]
    if subtitle:
        content.append(Paragraph(subtitle, styles["BannerSub"]))
    t = Table([[content]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PDF_BANNER_COLOR),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return [t, Spacer(1, 6 * mm)]


def _fit_logo_image(img_bytes, max_width, max_height):
    """Scales a logo to fit within max_width x max_height while preserving its
    real aspect ratio. A fixed square box would squish a wide horizontal logo
    lockup down to a sliver-thin strip - this sizes by the image's actual
    proportions instead, capped by whichever dimension is the tighter fit."""
    pil_img = PILImage.open(io.BytesIO(img_bytes))
    orig_w, orig_h = pil_img.size
    scale = min(max_width / orig_w, max_height / orig_h)
    return Image(io.BytesIO(img_bytes), width=orig_w * scale, height=orig_h * scale)


def _decode_logo(company, max_width, max_height):
    """Returns a sized Image flowable for the company logo, or "" if there's no
    logo or it can't be decoded. PIL decodes pixels lazily - constructing an
    Image() alone won't raise on a corrupt file, only a later render pass would
    (crashing the whole PDF) - so the decode is forced now, inside this
    try/except, letting a bad logo degrade to text-only instead."""
    data_url = (company or {}).get("logo_data_url") or ""
    if not (data_url.startswith("data:") and ";base64," in data_url):
        return ""
    try:
        _, b64data = data_url.split(";base64,", 1)
        img_bytes = base64.b64decode(b64data)
        PILImage.open(io.BytesIO(img_bytes)).load()
        return _fit_logo_image(img_bytes, max_width, max_height)
    except Exception:
        return ""


def company_header_block(company):
    """Optional header block (logo + company name) prepended to page 1 of every
    PDF export, above the title banner. Gated entirely by the global
    show_on_pdf toggle - callers just prepend this list to their story, never
    need an `if` themselves. The full address/contact details go in the page
    footer instead - see company_footer_line() - so this stays a clean,
    uncluttered logo-and-name strip."""
    if not company or not company.get("show_on_pdf"):
        return []

    name = company.get("name") or ""
    logo_cell = _decode_logo(company, max_width=65 * mm, max_height=20 * mm)
    if not name and not logo_cell:
        return []

    styles = pdf_styles()
    name_cell = Paragraph(name, styles["CompanyName"]) if name else ""

    if logo_cell and name_cell:
        # Name on the left, logo on the right - a common letterhead convention,
        # and keeps the logo from crowding straight into the page's left margin.
        row, col_widths = [[name_cell, logo_cell]], [110 * mm, 70 * mm]
        align_commands = [("ALIGN", (1, 0), (1, 0), "RIGHT")]
    else:
        row, col_widths = [[logo_cell or name_cell]], [180 * mm]
        align_commands = [("ALIGN", (0, 0), (0, 0), "RIGHT" if logo_cell else "LEFT")]

    t = Table(row, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        *align_commands,
    ]))
    return [t, Spacer(1, 5 * mm)]


def company_footer_line(company):
    """Name/address/contact line for the page footer (every page), centered,
    drawn below the page-number rule so it reads as a separate block rather
    than crowding the project/page-number line. Returns "" if disabled or
    empty - build_pdf_response/make_numbered_canvas treat an empty string as
    'draw nothing', so callers never need an `if` themselves."""
    if not company or not company.get("show_on_pdf"):
        return ""
    parts = [p for p in (
        company.get("name"), company.get("address"), company.get("phone"), company.get("email"), company.get("website"),
    ) if p]
    return " · ".join(parts)


def pdf_table_style(extra_commands=None):
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), PDF_BANNER_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_STRIPE_COLOR]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if extra_commands:
        commands += extra_commands
    return TableStyle(commands)


def checkbox_cell(checked=False, box_size=3.2 * mm):
    """A bordered box, filled with the accent color when checked - drawn
    rather than a Unicode glyph (e.g. "☐"/"☑"), since the base Helvetica
    fonts used throughout this design system (WinAnsi encoding) don't
    reliably render box-drawing characters. Used both for the old-style
    always-blank paper checkbox (checked=False, the default) and for
    reflecting real persisted checklist state (see routers/checkliste.py)."""
    t = Table([[""]], colWidths=[box_size], rowHeights=[box_size])
    style = [("BOX", (0, 0), (-1, -1), 0.8, PDF_BORDER_COLOR)]
    if checked:
        style.append(("BACKGROUND", (0, 0), (-1, -1), PDF_ACCENT_COLOR))
    t.setStyle(TableStyle(style))
    return t


def signature_block(label, styles):
    """A blank underline + caption, e.g. for 'Datum, Unterschrift Kunde'."""
    line = Table([[""]], colWidths=[80 * mm], rowHeights=[10 * mm])
    line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, PDF_BORDER_COLOR)]))
    return [line, Paragraph(label, styles["BodyMuted"])]


def make_numbered_canvas(footer_left_text, footer_center_text=""):
    """Canvas factory adding 'Seite X von Y' + a left-hand footer label to every
    page, plus an optional centered company address/contact line above it (see
    company_footer_line()). Needs a factory (not a plain class) because the
    total page count is only known once the whole document has been laid out -
    this defers drawing until save()."""

    class _NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfcanvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(page_count)
                pdfcanvas.Canvas.showPage(self)
            pdfcanvas.Canvas.save(self)

        def _draw_footer(self, page_count):
            width, _ = A4
            y_rule = 16 * mm
            self.setStrokeColor(PDF_BORDER_COLOR)
            self.line(15 * mm, y_rule, width - 15 * mm, y_rule)
            self.setFont("Helvetica", 8)
            self.setFillColor(PDF_MUTED_COLOR)
            self.drawString(15 * mm, y_rule - 5 * mm, footer_left_text)
            self.drawRightString(width - 15 * mm, y_rule - 5 * mm, f"Seite {self._pageNumber} von {page_count}")
            if footer_center_text:
                # Drawn below the project/page-number row, as its own separated
                # block, rather than crowding the same line.
                self.setFont("Helvetica", 8)
                self.setFillColor(PDF_MUTED_COLOR)
                self.drawCentredString(width / 2, y_rule - 10 * mm, footer_center_text)

    return _NumberedCanvas


def build_pdf_response(story, footer_left_text, filename, doc_title, footer_center_text=""):
    buf = io.BytesIO()
    # A centered company line needs its own row above the page-number rule -
    # give it a bit more bottom margin so it never crowds the last line of content.
    bottom_margin = 26 * mm if footer_center_text else 20 * mm
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=bottom_margin, leftMargin=15 * mm, rightMargin=15 * mm,
        title=doc_title,
    )
    doc.build(story, canvasmaker=make_numbered_canvas(footer_left_text, footer_center_text))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
