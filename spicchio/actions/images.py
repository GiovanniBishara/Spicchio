"""Image actions, built on Pillow."""

from __future__ import annotations

import io
import warnings
from pathlib import Path

from PIL import Image, ImageOps

from spicchio.actions.base import Action, ActionError, each, register
from spicchio.files import Kind, output_path

try:  # iPhone photos (HEIC); optional so the core keeps working without it
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

IMG = frozenset({Kind.IMAGE})

# Decompression bombs: a tiny file that claims to be gigapixels wide. Pillow warns
# above MAX_IMAGE_PIXELS; Spicchio refuses instead (120 MP still fits big panoramas).
Image.MAX_IMAGE_PIXELS = 120_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)


def _open(path: Path) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ActionError(f"{path.name} is too large to open safely") from exc
    except Exception as exc:  # Pillow raises many different errors for broken files
        raise ActionError(f"Can't read {path.name} as an image") from exc
    # Respect the camera orientation, then forget the EXIF flag.
    return ImageOps.exif_transpose(img)


def _flatten(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """Formats without transparency (JPG, PDF) need a solid background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, background)
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


def to_png(path: Path) -> Path:
    out = output_path(path, ".png")
    _open(path).save(out, "PNG", optimize=True)
    return out


def to_jpg(path: Path) -> Path:
    out = output_path(path, ".jpg")
    _flatten(_open(path)).save(out, "JPEG", quality=90, optimize=True, progressive=True)
    return out


def to_webp(path: Path) -> Path:
    out = output_path(path, ".webp")
    _open(path).save(out, "WEBP", quality=85, method=6)
    return out


def to_pdf(paths: list[Path]) -> list[Path]:
    """One image -> one PDF; several images -> a single PDF, one page each, in drop order."""
    pages = [_flatten(_open(p)) for p in paths]
    tag = "" if len(paths) == 1 else "album"
    out = output_path(paths[0], ".pdf", tag)
    pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return [out]


def compress(path: Path) -> Path:
    """Smaller file, same format when possible. PNG photos become JPG, which is what shrinks them."""
    img = _open(path)
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        out = output_path(path, ".jpg", "compressed")
        _flatten(img).save(out, "JPEG", quality=72, optimize=True, progressive=True)
    elif ext == ".webp":
        out = output_path(path, ".webp", "compressed")
        img.save(out, "WEBP", quality=70, method=6)
    elif img.mode in ("RGBA", "LA", "P"):
        # Graphics with transparency: keep PNG, reduce to 256 colours.
        out = output_path(path, ".png", "compressed")
        img.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(out, "PNG", optimize=True)
    else:
        out = output_path(path, ".jpg", "compressed")
        _flatten(img).save(out, "JPEG", quality=72, optimize=True, progressive=True)
    return out


def half_size(path: Path) -> Path:
    img = _open(path)
    w, h = img.size
    if w < 2 or h < 2:
        raise ActionError(f"{path.name} is too small to resize")
    out = output_path(path, path.suffix.lower(), "half")
    img.resize((w // 2, h // 2), Image.Resampling.LANCZOS).save(out)
    return out


def strip_metadata(path: Path) -> Path:
    """Rebuild the image from its pixels only: no EXIF, GPS, camera or software info."""
    img = _open(path)
    clean = Image.frombytes(img.mode, img.size, img.tobytes())
    if img.mode == "P":
        clean.putpalette(img.getpalette())
    out = output_path(path, path.suffix.lower(), "clean")
    clean.save(out)
    return out


def to_ico(path: Path) -> Path:
    """A Windows icon with every common size, from a centred square crop."""
    img = _open(path).convert("RGBA")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    square = img.crop((left, top, left + side, top + side))
    out = output_path(path, ".ico")
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(side, 16)]
    square.save(out, "ICO", sizes=sizes)
    return out


EMAIL_BYTES = 1_000_000


def email_size(path: Path) -> Path:
    """A JPG under 1 MB: the best quality that fits, shrinking the picture only if it must."""
    img = _flatten(_open(path))
    out = output_path(path, ".jpg", "email")

    def encode(im: Image.Image, q: int) -> bytes:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        return buf.getvalue()

    for _ in range(12):
        lo, hi, best = 35, 92, None
        while lo <= hi:  # binary search on quality
            q = (lo + hi) // 2
            data = encode(img, q)
            if len(data) <= EMAIL_BYTES:
                best, lo = data, q + 1
            else:
                hi = q - 1
        if best is not None:
            out.write_bytes(best)
            return out
        img = img.resize((max(1, int(img.width * 0.8)), max(1, int(img.height * 0.8))), Image.Resampling.LANCZOS)
    raise ActionError(f"Can't get {path.name} under 1 MB")


register(Action("img.pdf", "PDF", IMG, to_pdf, mode="many", title="Convert to PDF"))
register(Action("img.jpg", "JPG", IMG, each(to_jpg), skip_ext=frozenset({".jpg", ".jpeg"}), title="Convert to JPG"))
register(Action("img.png", "PNG", IMG, each(to_png), skip_ext=frozenset({".png"}), title="Convert to PNG"))
register(Action("img.webp", "WebP", IMG, each(to_webp), skip_ext=frozenset({".webp"}), title="Convert to WebP"))
register(Action("img.ico", "ICO", IMG, each(to_ico), skip_ext=frozenset({".ico"}), title="Windows icon"))
register(Action("img.compress", "Compress", IMG, each(compress), title="Make it smaller", side="tools"))
register(Action("img.email", "Under 1 MB", IMG, each(email_size), title="Ready for email", side="tools"))
register(Action("img.half", "Half size", IMG, each(half_size), title="Resize to 50%", side="tools"))
register(Action("img.clean", "No metadata", IMG, each(strip_metadata), title="Remove EXIF and GPS", side="tools"))
