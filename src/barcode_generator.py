from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from barcode import Code128
from barcode.writer import ImageWriter

from src.database.data_connection import get_users, get_prods
from src.skins import (
    DEFAULT_SKIN_KEY,
    get_skin_by_barcode,
    without_skin_products,
)


def get_codes_users():
    users = get_users()
    numbers = list(map(str, users["barcode"]))
    names = list(map(str, users["name"]))
    return numbers, names


def get_codes_prods(products=None):
    products = get_prods() if products is None else products
    stocked_products = without_skin_products(products)
    numbers = list(map(str, stocked_products["barcode"]))
    names = list(map(str, stocked_products["name"]))
    return numbers, names


def get_codes_skins(products=None):
    products = get_prods() if products is None else products
    codes = []
    for _, product in products.iterrows():
        skin = get_skin_by_barcode(product["barcode"])
        if skin is not None:
            codes.append((product, skin))
    return codes


def get_codes_mult():
    numbers = ["00", "02", "03", "04", "06", "10", "12", "24", "30", "60"]
    names = numbers.copy()
    names[0] = "Cancel Product"
    return numbers, names


def _user_barcode_label(number, name):
    """Keep every user label printable, including long single-word names."""

    name = str(name)
    if len(name) < 12:
        return f"{number} - {name}"

    parts = name.split()
    if not parts:
        return str(number)

    first_name = parts[0]
    if len(first_name) >= 12:
        first_name = f"{first_name[:11]}."
    initials = ".".join(part[0].upper() for part in parts[1:4])
    short_name = f"{first_name} {initials}." if initials else first_name
    return f"{number} - {short_name}"


def _price_text(price):
    if float(price).is_integer():
        return f"{int(price)} kr"
    return f"{float(price):.2f}".replace(".", ",") + " kr"


def _draw_skin_page(c, skin_codes):
    page_width, page_height = A4
    margin = 42

    c.setFillColor(colors.HexColor("#16261a"))
    c.roundRect(
        margin,
        page_height - 95,
        page_width - 2 * margin,
        50,
        8,
        fill=1,
        stroke=0,
    )
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(page_width / 2, page_height - 77, "CHECKOUT SKINS")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)
    c.drawCentredString(
        page_width / 2,
        page_height - 119,
        "Scan a checkout look. Paid skins contribute to the trip.",
    )
    c.drawCentredString(
        page_width / 2,
        page_height - 135,
        "Scan it during checkout; it activates when that checkout is finished.",
    )

    c.setFillColor(colors.HexColor("#fff1b8"))
    c.setStrokeColor(colors.HexColor("#6e5700"))
    c.roundRect(
        margin,
        page_height - 210,
        page_width - 2 * margin,
        55,
        7,
        fill=1,
        stroke=1,
    )
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(page_width / 2, page_height - 176, "LAST SKIN WINS")
    c.setFont("Helvetica", 10)
    c.drawCentredString(
        page_width / 2,
        page_height - 194,
        "The last skin scanned wins. Scan 00 immediately after it to cancel it.",
    )

    # Compact cards fit on one A4 sheet.
    card_height = 108
    card_gap = 8
    first_card_y = page_height - 330
    for index, (product, skin) in enumerate(skin_codes):
        y = first_card_y - index * (card_height + card_gap)
        c.setFillColor(colors.HexColor("#f2f5ef"))
        c.setStrokeColor(colors.HexColor("#435247"))
        c.roundRect(
            margin,
            y,
            page_width - 2 * margin,
            card_height,
            8,
            fill=1,
            stroke=1,
        )

        is_default_reset = skin.key == DEFAULT_SKIN_KEY
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        card_label = (
            "FREE RESET / CHECKOUT SKIN"
            if is_default_reset
            else "CHECKOUT SKIN / TRIP CONTRIBUTION"
        )
        c.drawString(margin + 16, y + 89, card_label)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margin + 16, y + 70, skin.name)
        c.setFont("Helvetica", 9)
        c.drawString(margin + 16, y + 54, skin.description)
        c.setFont("Helvetica-Bold", 11)
        price_label = (
            "FREE - RESET TO DEFAULT"
            if is_default_reset
            else f"Contribution: {_price_text(product['price'])}"
        )
        c.drawString(
            margin + 16,
            y + 34,
            price_label,
        )
        c.setFont("Helvetica", 8)
        action_label = (
            "RESTORE CLASSIC LOOK AFTER CHECKOUT"
            if is_default_reset
            else "BUY + ACTIVATE AFTER CHECKOUT"
        )
        c.drawString(margin + 16, y + 20, action_label)

        number = str(product["barcode"])
        barcode = Code128(number, writer=ImageWriter())
        barcode_x = page_width - margin - 238
        c.drawInlineImage(
            barcode.render(text="  "),
            x=barcode_x,
            y=y + 30,
            width=222,
            height=52,
            showBoundary=True,
        )
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            barcode_x + 111,
            y + 14,
            f"Barcode {number}",
        )


def generate_pdf(type, pdf_filename="output.pdf"):
    skin_codes = []
    if type == "users":
        numbers, names = get_codes_users()

    elif type == "prods":
        products = get_prods()
        numbers, names = get_codes_prods(products)
        skin_codes = get_codes_skins(products)

    elif type == "multipliers":
        numbers, names = get_codes_mult()

    else:
        return

    if type == "users":
        x_0, y_0 = 50, 740
        width_nr, height_nr = 4, 11
        step_x, step_y = 130, 70
        width, height = 120, 50

        x_text_displacement = lambda x: x + int(width / 2)
        y_text_displacement = lambda y: y + 2
        font_size = 11
        show_boundary = True

        text_func = _user_barcode_label

    else:
        x_0, y_0 = 300, 720
        width_nr, height_nr = 1, 10
        step_x, step_y = 120, 70
        width, height = 200, 50

        x_text_displacement = lambda x: x - 100
        y_text_displacement = lambda y: y + int(height / 2)
        text_func = lambda x, y: f"{y}"
        font_size = 30
        show_boundary = False

    # Create PDF
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    c.setFontSize(font_size)
    total_barcodes = width_nr * height_nr
    for i, number in enumerate(numbers):
        barcode = Code128(number, writer=ImageWriter())
        barcode_count = i % total_barcodes

        # Move to the next page
        if i != 0 and i % total_barcodes == 0:
            c.showPage()
            c.setFontSize(font_size)

        x = x_0 + (barcode_count % width_nr) * step_x
        y = y_0 - ((barcode_count // width_nr)) * step_y

        # Add barcode to PDF
        c.drawInlineImage(
            barcode.render(text="  "),
            x=x,
            y=y,
            width=width,
            height=height,
            showBoundary=show_boundary,
        )
        c.drawCentredString(
            x=x_text_displacement(x),
            y=y_text_displacement(y),
            text=text_func(number, names[i]),
        )

    if skin_codes:
        if numbers:
            c.showPage()
        _draw_skin_page(c, skin_codes)
    c.save()


if __name__ == "__main__":
    # Example usage
    generate_pdf("multipliers")
