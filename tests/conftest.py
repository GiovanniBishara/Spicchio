from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    """A 64x48 RGB JPEG with EXIF data."""
    p = tmp_path / "photo.jpg"
    img = Image.new("RGB", (64, 48), (200, 80, 30))
    exif = Image.Exif()
    exif[0x010F] = "Spicchio Camera"  # Make
    img.save(p, "JPEG", exif=exif)
    return p


@pytest.fixture
def logo(tmp_path: Path) -> Path:
    """A 40x40 PNG with transparency."""
    p = tmp_path / "logo.png"
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(10, 30):
        for y in range(10, 30):
            img.putpixel((x, y), (108, 60, 255, 255))
    img.save(p, "PNG")
    return p


@pytest.fixture
def pdf3(tmp_path: Path) -> Path:
    """A three-page PDF with real text."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    p = tmp_path / "report.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    for i in range(1, 4):
        c.drawString(72, 750, f"Page {i} of the Spicchio report")
        c.showPage()
    c.save()
    return p
