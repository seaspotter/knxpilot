"""
Avery Zweckform L6037 label-sheet PDF generator - used by the Abgangsliste's
"Etiketten" export (backend/routers/abgangsliste.py). L6037 is 25.4 x 10 mm
labels, 7 columns x 27 rows = 189 per A4 sheet. Avery's own site doesn't
publish machine-readable layout specs (x0/y0/dx/dy); the values below match
the internationally-equivalent "8658" template family used by third-party
label-template databases for this exact size/count and are the standard
reference for it - still worth a plain-paper test print (debug=True) before
committing to real label stock, since printers vary by up to ~1mm.
"""
import io

from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

L6037_COLS = 7
L6037_ROWS = 27
L6037_PER_SHEET = L6037_COLS * L6037_ROWS  # 189

_LABEL_W = 25.4 * mm
_LABEL_H = 10 * mm
_X0 = 5 * mm  # left edge of the page to the first label's left edge
_Y0 = 13 * mm  # top edge of the page to the first label's top edge
_DX = 28.5 * mm  # horizontal distance between label origins
_DY = 10.14 * mm  # vertical distance between label origins
_RADIUS = 1 * mm


def _label_origin(index_on_sheet):
    """index_on_sheet: 0-based position within one sheet (0..188), filled
    row-major (left-to-right, top-to-bottom, matching how the labels are
    physically numbered on a real Avery sheet). Returns the label's
    bottom-left corner in PDF coordinates (origin bottom-left of page)."""
    row, col = divmod(index_on_sheet, L6037_COLS)
    _, page_h = A4
    x = _X0 + col * _DX
    y = page_h - (_Y0 + row * _DY) - _LABEL_H
    return x, y


def render_label_sheet(items, filename, start=1, debug=False):
    """
    items: list of (line1, line2) string tuples, one per label, in order.
    start: 1-based position on the FIRST sheet to begin filling at (to
    resume a partially-used sheet) - every following sheet starts fresh at
    position 1.
    debug: draws a light border and the position number on every label -
    for a plain-paper test print to check alignment against a real blank
    sheet before printing on actual label stock.
    """
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)

    pos = max(1, min(start, L6037_PER_SHEET)) - 1  # 0-based index on current sheet
    for line1, line2 in items:
        if pos >= L6037_PER_SHEET:
            c.showPage()
            pos = 0
        x, y = _label_origin(pos)
        if debug:
            c.setLineWidth(0.3)
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.roundRect(x, y, _LABEL_W, _LABEL_H, _RADIUS, stroke=1, fill=0)
            c.setFont("Helvetica", 4)
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.drawString(x + 0.8 * mm, y + 0.8 * mm, str(pos + 1))
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + _LABEL_W / 2, y + _LABEL_H - 4.3 * mm, (line1 or "")[:22])
        c.setFont("Helvetica", 6)
        c.drawCentredString(x + _LABEL_W / 2, y + 1.7 * mm, (line2 or "")[:26])
        pos += 1

    c.save()
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
