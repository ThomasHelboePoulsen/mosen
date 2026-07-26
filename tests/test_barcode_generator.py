from barcode import Code128
from src import barcode_generator
from barcode.writer import ImageWriter


def test_generate_pdf_does_not_require_barcode_caption_font(tmp_path, monkeypatch):
    # Arrange
    missing_font = tmp_path / "missing-barcode-font.ttf"

    def image_writer_without_font():
        writer = ImageWriter()
        writer.font_path = str(missing_font)
        return writer

    monkeypatch.setattr(barcode_generator, "ImageWriter", image_writer_without_font)
    monkeypatch.setattr(
        barcode_generator,
        "get_codes_users",
        lambda: (["1000"], ["Thomas"]),
    )
    output = tmp_path / "users.pdf"

    # Act
    barcode_generator.generate_pdf("users", str(output))

    # Assert
    assert output.read_bytes().startswith(b"%PDF")


def test_barcode_image_reserves_blank_space_for_reportlab_label(tmp_path):
    # Arrange
    writer = ImageWriter()
    writer.font_path = str(tmp_path / "missing-barcode-font.ttf")

    # Act
    image = Code128("1000", writer=writer).render(
        writer_options=barcode_generator._BARCODE_RENDER_OPTIONS
    )
    bottom_quarter = image.crop(
        (0, int(image.height * 0.75), image.width, image.height)
    )

    # Assert
    assert all(channel == (255, 255) for channel in bottom_quarter.getextrema())
