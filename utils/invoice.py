"""Invoice PDF generation with ReportLab."""

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config.settings import settings
from models.entities import Order


def build_invoice_pdf(order: Order) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{settings.app_name}</b> — Tax Invoice", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Invoice: <b>{order.invoice_number or 'N/A'}</b>", styles["Normal"]))
    story.append(Paragraph(f"Order: <b>{order.order_number}</b>", styles["Normal"]))
    story.append(Paragraph(f"Date: {order.created_at}", styles["Normal"]))
    story.append(Paragraph(f"Status: {order.status.value}", styles["Normal"]))
    story.append(Spacer(1, 12))

    rows = [["Item", "SKU", "Qty", "Unit", "Total"]]
    for item in order.items:
        rows.append(
            [
                f"{item.product_name} ({item.variant_name})",
                item.sku,
                str(item.quantity),
                f"₹{item.unit_price}",
                f"₹{item.line_total}",
            ]
        )
    table = Table(rows, colWidths=[70 * mm, 30 * mm, 15 * mm, 25 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2545")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 14))

    totals = [
        ["Subtotal", f"₹{order.subtotal}"],
        ["Discount", f"-₹{order.discount_amount}"],
        ["Shipping", f"₹{order.shipping_amount}"],
        ["Tax", f"₹{order.tax_amount}"],
        ["Grand Total", f"₹{order.total}"],
    ]
    t2 = Table(totals, colWidths=[140 * mm, 30 * mm])
    t2.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0b2545")),
            ]
        )
    )
    story.append(t2)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Thank you for shopping with us.", styles["Italic"]))

    doc.build(story)
    return buffer.getvalue()


def save_invoice_pdf(order: Order) -> Path:
    out_dir = Path(settings.upload_dir) / "invoices"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{order.invoice_number or order.order_number}.pdf"
    path.write_bytes(build_invoice_pdf(order))
    return path
