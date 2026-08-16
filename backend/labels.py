"""
Label-sheet PDF generator - used by the "Labels" project sub-tab's export
(backend/routers/abgangsliste.py). LABEL_FORMATS holds the layout for each
supported sheet; only Avery Zweckform L6037 exists today, but the registry
shape means a second format is just a new dict entry here plus a new
<option> in frontend/index.html's #label-format select (and an entry in
frontend/js/labels.js's LABEL_FORMAT_SIZES).

L6037 is 25.4 x 10 mm labels, 7 columns x 27 rows = 189 per A4 sheet.
Avery's own site doesn't publish machine-readable layout specs (x0/y0/dx/
dy); the values below match the internationally-equivalent "8658" template
family used by third-party label-template databases for this exact size/
count and are the standard reference for it - still worth a plain-paper
test print (debug=True) before committing to real label stock, since
printers vary by up to ~1mm.
"""
import io

from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

LABEL_FORMATS = {
    "l6037": {
        "name": "Avery Zweckform L6037 (25,4 × 10 mm)",
        "cols": 7,
        "rows": 27,
        "label_w": 25.4 * mm,
        "label_h": 10 * mm,
        "x0": 5 * mm,  # left edge of the page to the first label's left edge
        "y0": 13 * mm,  # top edge of the page to the first label's top edge
        "dx": 28.5 * mm,  # horizontal distance between label origins
        "dy": 10.14 * mm,  # vertical distance between label origins
        "radius": 1 * mm,
    },
}


def _label_origin(fmt, index_on_sheet):
    """index_on_sheet: 0-based position within one sheet, filled row-major
    (left-to-right, top-to-bottom, matching how the labels are physically
    numbered on a real sheet). Returns the label's bottom-left corner in
    PDF coordinates (origin bottom-left of page)."""
    row, col = divmod(index_on_sheet, fmt["cols"])
    _, page_h = A4
    x = fmt["x0"] + col * fmt["dx"]
    y = page_h - (fmt["y0"] + row * fmt["dy"]) - fmt["label_h"]
    return x, y


def render_label_sheet(items, filename, format="l6037", start=1, debug=False):
    """
    items: list of (line1, line2) string tuples, one per label, in order.
    format: key into LABEL_FORMATS.
    start: 1-based position on the FIRST sheet to begin filling at (to
    resume a partially-used sheet) - every following sheet starts fresh at
    position 1.
    debug: draws a light border and the position number on every label -
    for a plain-paper test print to check alignment against a real blank
    sheet before printing on actual label stock.
    """
    fmt = LABEL_FORMATS[format]
    per_sheet = fmt["cols"] * fmt["rows"]
    label_w, label_h, radius = fmt["label_w"], fmt["label_h"], fmt["radius"]

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)

    pos = max(1, min(start, per_sheet)) - 1  # 0-based index on current sheet
    for line1, line2 in items:
        if pos >= per_sheet:
            c.showPage()
            pos = 0
        x, y = _label_origin(fmt, pos)
        if debug:
            c.setLineWidth(0.3)
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.roundRect(x, y, label_w, label_h, radius, stroke=1, fill=0)
            c.setFont("Helvetica", 4)
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.drawString(x + 0.8 * mm, y + 0.8 * mm, str(pos + 1))
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + label_w / 2, y + label_h - 4.3 * mm, (line1 or "")[:22])
        c.setFont("Helvetica", 6)
        c.drawCentredString(x + label_w / 2, y + 1.7 * mm, (line2 or "")[:26])
        pos += 1

    c.save()
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
