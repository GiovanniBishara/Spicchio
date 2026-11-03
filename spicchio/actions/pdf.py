"""PDF actions: pypdf for structure, pypdfium2 to render pages as images."""

from __future__ import annotations

from pathlib import Path

from spicchio.actions.base import Action, ActionError, each, register
from spicchio.files import Kind, output_dir, output_path

PDF = frozenset({Kind.PDF})
RENDER_PIXELS = 40_000_000  # per page: a crafted page size can't ask for gigabytes of memory


def _reader(path: Path):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ActionError(f"{path.name} is password protected")
        _ = len(reader.pages)
        return reader
    except PdfReadError as exc:
        raise ActionError(f"Can't read {path.name} as a PDF") from exc


def merge(paths: list[Path]) -> list[Path]:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for p in paths:
        writer.append(_reader(p))
    out = output_path(paths[0], ".pdf", "merged")
    with out.open("wb") as f:
        writer.write(f)
    return [out]


def split(path: Path) -> list[Path]:
    from pypdf import PdfWriter

    reader = _reader(path)
    if len(reader.pages) < 2:
        raise ActionError(f"{path.name} has only one page")
    folder = output_dir(path, "pages")
    width = len(str(len(reader.pages)))
    outs = []
    for i, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out = folder / f"{path.stem}-{i:0{width}d}.pdf"
        with out.open("wb") as f:
            writer.write(f)
        outs.append(out)
    return outs


def rotate(path: Path) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=_reader(path))
    for page in writer.pages:
        page.rotate(90)
    out = output_path(path, ".pdf", "rotated")
    with out.open("wb") as f:
        writer.write(f)
    return out


def compress(path: Path) -> Path:
    """Lossless clean-up plus recompression of embedded photos at JPEG quality 70."""
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=_reader(path))
    for page in writer.pages:
        page.compress_content_streams()
        for img in page.images:
            try:
                if img.image is not None and img.image.mode in ("RGB", "L"):
                    img.replace(img.image, quality=70)
            except Exception:
                continue  # leave unusual image encodings untouched
    writer.compress_identical_objects()  # defaults: drop duplicate and unreferenced objects
    out = output_path(path, ".pdf", "compressed")
    with out.open("wb") as f:
        writer.write(f)
    return out


def to_images(path: Path) -> list[Path]:
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        raise ActionError(f"Can't read {path.name} as a PDF") from exc
    n = len(doc)
    if n == 1:
        targets = [output_path(path, ".png")]
    else:
        folder = output_dir(path, "images")
        width = len(str(n))
        targets = [folder / f"{path.stem}-{i:0{width}d}.png" for i in range(1, n + 1)]
    for page, target in zip(doc, targets, strict=True):
        w, h = page.get_size()  # points
        scale = min(2.0, (RENDER_PIXELS / max(w * h, 1.0)) ** 0.5)
        page.render(scale=scale).to_pil().save(target, "PNG", optimize=True)
    doc.close()
    return targets


def to_text(path: Path) -> Path:
    reader = _reader(path)
    text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    if not text:
        raise ActionError(f"{path.name} has no selectable text (it may be a scan)")
    out = output_path(path, ".txt")
    out.write_text(text + "\n", encoding="utf-8")
    return out


register(Action("pdf.png", "Images", PDF, each(to_images), title="Pages to PNG"))
register(Action("pdf.text", "Text", PDF, each(to_text), title="Extract the text"))
register(Action("pdf.merge", "Merge", PDF, merge, mode="many", min_files=2, title="Merge into one PDF", side="tools"))
register(Action("pdf.compress", "Compress", PDF, each(compress), title="Make it smaller", side="tools"))
register(Action("pdf.split", "Split pages", PDF, each(split), title="One PDF per page", side="tools"))
register(Action("pdf.rotate", "Rotate", PDF, each(rotate), title="Rotate 90°", side="tools"))
