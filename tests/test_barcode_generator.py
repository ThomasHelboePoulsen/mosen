import pandas as pd

from src import barcode_generator


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))

    def setFontSize(self, *args, **kwargs):
        self._record("setFontSize", *args, **kwargs)

    def setFont(self, *args, **kwargs):
        self._record("setFont", *args, **kwargs)

    def setFillColor(self, *args, **kwargs):
        self._record("setFillColor", *args, **kwargs)

    def setStrokeColor(self, *args, **kwargs):
        self._record("setStrokeColor", *args, **kwargs)

    def roundRect(self, *args, **kwargs):
        self._record("roundRect", *args, **kwargs)

    def drawString(self, *args, **kwargs):
        self._record("drawString", *args, **kwargs)

    def drawCentredString(self, *args, **kwargs):
        self._record("drawCentredString", *args, **kwargs)

    def drawInlineImage(self, *args, **kwargs):
        self._record("drawInlineImage", *args, **kwargs)

    def showPage(self, *args, **kwargs):
        self._record("showPage", *args, **kwargs)

    def save(self, *args, **kwargs):
        self._record("save", *args, **kwargs)


class FakeBarcode:
    def __init__(self, number, writer):
        self.number = number

    def render(self, text):
        return f"barcode-image-{self.number}"


def _product(barcode, name, price=10):
    return {
        "barcode": barcode,
        "name": name,
        "price": price,
        "category": "Other",
        "current_stock": 0,
        "initial_stock": 0,
    }


def _recording_pdf(monkeypatch, products):
    recording = RecordingCanvas()
    monkeypatch.setattr(barcode_generator, "get_prods", lambda: products)
    monkeypatch.setattr(
        barcode_generator.canvas,
        "Canvas",
        lambda *args, **kwargs: recording,
    )
    monkeypatch.setattr(barcode_generator, "Code128", FakeBarcode)
    monkeypatch.setattr(barcode_generator, "ImageWriter", lambda: object())
    barcode_generator.generate_pdf("prods", "ignored.pdf")
    return recording


def _text_calls(recording):
    texts = []
    for name, args, kwargs in recording.calls:
        if name not in {"drawString", "drawCentredString"}:
            continue
        texts.append(args[2] if len(args) >= 3 else kwargs["text"])
    return texts


def test_product_codes_partition_stocked_products_and_skins():
    products = pd.DataFrame(
        [
            _product(101, "Water"),
            _product(900, "Deep Swamp", price=4),
            _product(102, "Soda"),
        ]
    )

    numbers, names = barcode_generator.get_codes_prods(products)
    skins = barcode_generator.get_codes_skins(products)

    assert numbers == ["101", "102"]
    assert names == ["Water", "Soda"]
    assert len(skins) == 1
    product, skin = skins[0]
    assert product.to_dict() == _product(900, "Deep Swamp", price=4)
    assert skin == barcode_generator.get_skin_by_barcode(900)


def test_stocked_product_pdf_layout_is_unchanged(monkeypatch):
    recording = _recording_pdf(
        monkeypatch,
        pd.DataFrame([_product(101, "Water")]),
    )

    image_call = next(call for call in recording.calls if call[0] == "drawInlineImage")

    assert image_call[1][0] == "barcode-image-101"
    assert image_call[2] == {
        "x": 300,
        "y": 720,
        "width": 200,
        "height": 50,
        "showBoundary": False,
    }
    assert _text_calls(recording) == ["Water"]
    assert not any(call[0] == "showPage" for call in recording.calls)


def test_skin_products_get_a_separate_explanatory_page(monkeypatch):
    products = pd.DataFrame(
        [
            _product(101, "Water"),
            _product(903, "Default checkout", price=0),
            _product(900, "Deep Swamp", price=4),
            _product(901, "Bog Terminal", price=2.5),
            _product(902, "Neon Bog", price=3),
        ]
    )

    recording = _recording_pdf(monkeypatch, products)
    texts = _text_calls(recording)
    images = [call[1][0] for call in recording.calls if call[0] == "drawInlineImage"]

    assert sum(call[0] == "showPage" for call in recording.calls) == 1
    assert images == [
        "barcode-image-101",
        "barcode-image-903",
        "barcode-image-900",
        "barcode-image-901",
        "barcode-image-902",
    ]
    assert "CHECKOUT SKINS" in texts
    assert "LAST SKIN WINS" in texts
    assert (
        "The last skin scanned wins. Scan 00 immediately after it to cancel it."
        in texts
    )
    assert "Contribution: 4 kr" in texts
    assert "Contribution: 2,50 kr" in texts
    assert "FREE RESET / CHECKOUT SKIN" in texts
    assert "FREE - RESET TO DEFAULT" in texts
    assert "RESTORE CLASSIC LOOK AFTER CHECKOUT" in texts
    assert "BUY + ACTIVATE AFTER CHECKOUT" in texts
    assert not any(text.startswith("PAGE ") for text in texts)
    skin_images = [
        call for call in recording.calls if call[0] == "drawInlineImage"
    ][1:]
    assert all(call[2]["y"] >= 42 for call in skin_images)
    skin_cards = [
        call
        for call in recording.calls
        if call[0] == "roundRect" and call[1][3] == 108
    ]
    assert len(skin_cards) == 4
    assert min(call[1][1] for call in skin_cards) >= 42


def test_skin_only_pdf_does_not_start_with_a_blank_page(monkeypatch):
    recording = _recording_pdf(
        monkeypatch,
        pd.DataFrame([_product(900, "Deep Swamp", price=4)]),
    )

    assert not any(call[0] == "showPage" for call in recording.calls)
    assert "CHECKOUT SKINS" in _text_calls(recording)


def test_user_barcode_pdf_layout_is_unchanged(monkeypatch):
    recording = RecordingCanvas()
    monkeypatch.setattr(
        barcode_generator,
        "get_users",
        lambda: pd.DataFrame([{"barcode": 1000, "name": "Ada"}]),
    )
    monkeypatch.setattr(
        barcode_generator.canvas,
        "Canvas",
        lambda *args, **kwargs: recording,
    )
    monkeypatch.setattr(barcode_generator, "Code128", FakeBarcode)
    monkeypatch.setattr(barcode_generator, "ImageWriter", lambda: object())

    barcode_generator.generate_pdf("users", "ignored.pdf")

    image_call = next(call for call in recording.calls if call[0] == "drawInlineImage")
    assert image_call[1][0] == "barcode-image-1000"
    assert image_call[2] == {
        "x": 50,
        "y": 740,
        "width": 120,
        "height": 50,
        "showBoundary": True,
    }
    assert _text_calls(recording) == ["1000 - Ada"]


def test_long_single_word_user_name_always_gets_a_printable_label(monkeypatch):
    recording = RecordingCanvas()
    monkeypatch.setattr(
        barcode_generator,
        "get_users",
        lambda: pd.DataFrame(
            [{"barcode": 1000, "name": "Christoffersen"}]
        ),
    )
    monkeypatch.setattr(
        barcode_generator.canvas,
        "Canvas",
        lambda *args, **kwargs: recording,
    )
    monkeypatch.setattr(barcode_generator, "Code128", FakeBarcode)
    monkeypatch.setattr(barcode_generator, "ImageWriter", lambda: object())

    barcode_generator.generate_pdf("users", "ignored.pdf")

    assert _text_calls(recording) == ["1000 - Christoffer."]


def test_real_skin_pdf_can_be_rendered(tmp_path, monkeypatch):
    products = pd.DataFrame(
        [
            _product(101, "Water"),
            _product(903, "Default checkout", price=0),
            _product(900, "Deep Swamp", price=4),
            _product(901, "Bog Terminal", price=2.5),
            _product(902, "Neon Bog", price=3),
        ]
    )
    output = tmp_path / "product_barcodes.pdf"
    monkeypatch.setattr(barcode_generator, "get_prods", lambda: products)

    barcode_generator.generate_pdf("prods", str(output))

    pdf_bytes = output.read_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 5_000
