from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from openpyxl import Workbook
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from polka.services import STATUS_LABELS


def document_pdf(order):
    if "Polka" not in pdfmetrics.getRegisteredFontNames():
        fonts = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/TTF/DejaVuSans.ttf")]
        font = next((f for f in fonts if f.exists()), None)
        if not font:
            raise RuntimeError("Для PDF установите шрифт DejaVu Sans")
        pdfmetrics.registerFont(TTFont("Polka", str(font)))
    output = BytesIO()
    style = ParagraphStyle("Основной", fontName="Polka", fontSize=10, leading=15)
    heading = ParagraphStyle("Заголовок", parent=style, fontSize=23, leading=29, textColor=colors.HexColor("#26362d"))
    rows = [["Товар", "Кол-во", "Цена, ₽", "Сумма, ₽"]]
    for item in order.items:
        rows.append([Paragraph(escape(item.name), style), str(item.quantity), f"{item.price:.2f}", f"{item.price * item.quantity:.2f}"])
    table = Table(rows, colWidths=[250, 55, 85, 85], repeatRows=1)
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "Polka"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eae8df")), ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph("ПОЛКА", heading), Spacer(1, 15), Paragraph(f"Лист заказа №{order.id:06d}", heading), Spacer(1, 15), Paragraph(f"Получатель: {escape(order.recipient)}", style), Paragraph(f"Адрес: {escape(order.address)}", style), Paragraph(f"Телефон: {escape(order.phone)}", style), Paragraph(f"Статус: {STATUS_LABELS[order.status]}", style), Spacer(1, 20), table, Spacer(1, 15), Paragraph(f"Итого: {order.total:.2f} ₽ · Оплата при получении", style)]
    SimpleDocTemplate(output, title=f"Заказ №{order.id}", author="Полка", leftMargin=40, rightMargin=40).build(story)
    return output.getvalue()


def sales_excel(orders):
    book = Workbook()
    sheet = book.active
    sheet.title = "Продажи"
    sheet.append(["Заказ", "Дата доставки", "Получатель", "Количество товаров", "Сумма, ₽"])
    for order in orders:
        # Строки из пользовательских полей записываются как текст, без формул Excel.
        name = order.recipient
        if name.startswith(("=", "+", "-", "@")):
            name = "'" + name
        sheet.append([order.id, order.delivered_at.isoformat(), name, sum(i.quantity for i in order.items), float(order.total)])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for col, width in zip("ABCDE", [15, 30, 32, 24, 20]):
        sheet.column_dimensions[col].width = width
    for row in sheet.iter_rows(min_row=2, min_col=5, max_col=5):
        row[0].number_format = '#,##0.00'
    output = BytesIO()
    book.save(output)
    return output.getvalue()
