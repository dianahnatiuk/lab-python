"""Генерація PDF з результатами аналізів (reportlab + DejaVu для кирилиці)."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.lab import Order

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FLAG_LABELS = {"low": "нижче норми", "high": "вище норми", "normal": "норма"}
FLAG_COLORS = {"low": colors.HexColor("#0b5ed7"), "high": colors.HexColor("#b3261e")}
_fonts_ready = False


def _register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    _fonts_ready = True


def _fmt_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def _num(value: float) -> str:
    return f"{value:g}"


def build_pdf(order: Order, results: dict) -> bytes:
    _register_fonts()
    patient = order.patient

    title = ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=16, leading=20)
    body = ParagraphStyle("body", fontName="DejaVu", fontSize=10, leading=14)
    small = ParagraphStyle(
        "small", fontName="DejaVu", fontSize=8, leading=11, textColor=colors.grey
    )

    info_rows = [
        ["Пацієнт:", patient.full_name],
        ["Дата народження:", _fmt_date(patient.birth_date)],
        ["Номер замовлення:", f"{order.id} ({order.barcode})"],
        ["Дата замовлення:", order.created_at.strftime("%d.%m.%Y %H:%M")],
        ["Результат готовий:", results["entered_at"].strftime("%d.%m.%Y %H:%M")],
    ]
    info = Table(info_rows, colWidths=[45 * mm, 120 * mm])
    info.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "DejaVu-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "DejaVu"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    rows = [["Показник", "Результат", "Од. вим.", "Норма", "Оцінка"]]
    styles = [
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef7")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5cbd3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i, t in enumerate(results["tests"], start=1):
        rows.append(
            [
                t["name"],
                _num(t["value"]),
                t["unit"],
                f"{_num(t['ref_min'])} – {_num(t['ref_max'])}",
                FLAG_LABELS.get(t["flag"], t["flag"]),
            ]
        )
        if t["flag"] in FLAG_COLORS:
            styles.append(("TEXTCOLOR", (4, i), (4, i), FLAG_COLORS[t["flag"]]))
            styles.append(("FONTNAME", (1, i), (1, i), "DejaVu-Bold"))
    table = Table(rows, colWidths=[55 * mm, 25 * mm, 28 * mm, 32 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle(styles))

    story = [
        Paragraph("MedLab — результати лабораторних аналізів", title),
        Spacer(1, 8 * mm),
        info,
        Spacer(1, 6 * mm),
        table,
    ]
    if results.get("conclusion"):
        story += [
            Spacer(1, 6 * mm),
            Paragraph(f"<b>Висновок:</b> {escape(results['conclusion'])}", body),
        ]
    story += [
        Spacer(1, 10 * mm),
        Paragraph("Документ сформовано автоматично. Інтерпретацію результатів надає лікар.", small),
    ]

    buffer = BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        title=f"Результати аналізів {order.barcode}",
    ).build(story)
    return buffer.getvalue()
