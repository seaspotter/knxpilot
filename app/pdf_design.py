"""
Shared PDF design system - used by every PDF export (Abgangsliste,
Geräteliste, Pflichtenheft) so they all look consistent: a dark banner
header, a light table style, and a footer with "Seite X von Y" + project
name on every page.
"""
import io

from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as pdfcanvas

PDF_BANNER_COLOR = colors.HexColor("#1e293b")
PDF_ACCENT_COLOR = colors.HexColor("#0284c7")
PDF_MUTED_COLOR = colors.HexColor("#64748b")
PDF_BORDER_COLOR = colors.HexColor("#cbd5e1")
PDF_STRIPE_COLOR = colors.HexColor("#f1f5f9")


def pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("BannerTitle", fontName="Helvetica-Bold", fontSize=18, textColor=colors.white, leading=22))
    styles.add(ParagraphStyle("BannerSub", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#cbd5e1"), leading=14))
    styles.add(ParagraphStyle("SectionHeading", fontName="Helvetica-Bold", fontSize=13, textColor=PDF_BANNER_COLOR, spaceBefore=10, spaceAfter=4))
    styles.add(ParagraphStyle("RoomHeading", fontName="Helvetica-Bold", fontSize=11, textColor=PDF_ACCENT_COLOR, spaceBefore=6, spaceAfter=2))
    styles.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#0f172a"), leading=13))
    styles.add(ParagraphStyle("BodyMuted", fontName="Helvetica-Oblique", fontSize=9, textColor=PDF_MUTED_COLOR, leading=12))
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


def make_numbered_canvas(footer_left_text):
    """Canvas factory adding 'Seite X von Y' + a left-hand footer label to every page.
    Needs a factory (not a plain class) because the total page count is only known
    once the whole document has been laid out - this defers drawing until save()."""

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
            self.setStrokeColor(PDF_BORDER_COLOR)
            self.line(15 * mm, 14 * mm, width - 15 * mm, 14 * mm)
            self.setFont("Helvetica", 8)
            self.setFillColor(PDF_MUTED_COLOR)
            self.drawString(15 * mm, 9 * mm, footer_left_text)
            self.drawRightString(width - 15 * mm, 9 * mm, f"Seite {self._pageNumber} von {page_count}")

    return _NumberedCanvas


def build_pdf_response(story, footer_left_text, filename, doc_title):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=20 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
        title=doc_title,
    )
    doc.build(story, canvasmaker=make_numbered_canvas(footer_left_text))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
