import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from spicchio.actions import SIDES, ActionError, Done, actions_for, all_actions, get, sides_for
from spicchio.actions.media import has_ffmpeg
from spicchio.cli import main as cli


def ids(paths):
    return [a.id for a in actions_for(paths)]


# --- which slices appear -------------------------------------------------

def test_no_slice_converts_a_file_to_its_own_format(photo: Path, logo: Path):
    assert "img.jpg" not in ids([photo])
    assert "img.png" not in ids([logo])
    assert "img.png" in ids([photo])


def test_merge_needs_two_pdfs(pdf3: Path, tmp_path: Path):
    assert "pdf.merge" not in ids([pdf3])
    other = tmp_path / "other.pdf"
    other.write_bytes(pdf3.read_bytes())
    assert actions_for([pdf3, other], "tools")[0].id == "pdf.merge"


def test_mixed_files_only_get_generic_actions(photo: Path, pdf3: Path):
    assert [side for side, _ in sides_for([photo, pdf3])] == ["actions"]
    assert ids([photo, pdf3]) == ["any.zip", "any.path", "any.terminal", "any.sha256"]


def test_every_side_fits_on_the_wheel(photo: Path, pdf3: Path):
    for files in ([photo], [pdf3], [photo, photo]):
        for side, acts in sides_for(files):
            assert side in SIDES and 1 <= len(acts) <= 8


def test_sides_come_in_order(photo: Path):
    assert [side for side, _ in sides_for([photo])] == ["convert", "tools", "actions"]
    assert [a.id for a in actions_for([photo], "convert")][0] == "img.pdf"


def test_action_ids_are_unique():
    all_ids = [a.id for a in all_actions()]
    assert len(all_ids) == len(set(all_ids))


# --- images --------------------------------------------------------------

def test_png_with_transparency_to_jpg_gets_white_background(logo: Path):
    (out,) = get("img.jpg")([logo])
    img = Image.open(out)
    assert out.suffix == ".jpg" and img.mode == "RGB"
    assert img.getpixel((1, 1))[0] > 240  # transparent corner became white


def test_images_to_one_pdf_keep_order(photo: Path, logo: Path):
    (out,) = get("img.pdf")([photo, logo])
    assert out.name == "photo-album.pdf"
    assert len(PdfReader(out).pages) == 2


def test_compress_keeps_original_and_shrinks(tmp_path: Path):
    src = tmp_path / "big.jpg"
    noise = Image.effect_noise((600, 400), 80).convert("RGB")
    noise.save(src, "JPEG", quality=98)
    (out,) = get("img.compress")([src])
    assert src.exists() and out.name == "big-compressed.jpg"
    assert out.stat().st_size < src.stat().st_size


def test_half_size(photo: Path):
    (out,) = get("img.half")([photo])
    assert Image.open(out).size == (32, 24)


def test_strip_metadata_removes_exif(photo: Path):
    assert Image.open(photo).getexif()
    (out,) = get("img.clean")([photo])
    assert not Image.open(out).getexif()


def test_broken_image_gives_a_readable_error(tmp_path: Path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(ActionError, match="broken.png"):
        get("img.jpg")([bad])


def test_converting_twice_does_not_overwrite(photo: Path):
    (a,) = get("img.png")([photo])
    (b,) = get("img.png")([photo])
    assert a.name == "photo.png" and b.name == "photo (1).png"


# --- pdf -----------------------------------------------------------------

def test_split_creates_one_pdf_per_page(pdf3: Path):
    outs = get("pdf.split")([pdf3])
    assert [o.name for o in outs] == ["report-1.pdf", "report-2.pdf", "report-3.pdf"]
    assert all(len(PdfReader(o).pages) == 1 for o in outs)
    assert outs[0].parent.name == "report-pages"


def test_merge_then_rotate(pdf3: Path, tmp_path: Path):
    other = tmp_path / "other.pdf"
    other.write_bytes(pdf3.read_bytes())
    (merged,) = get("pdf.merge")([pdf3, other])
    assert len(PdfReader(merged).pages) == 6
    (rotated,) = get("pdf.rotate")([merged])
    assert PdfReader(rotated).pages[0].rotation == 90


def test_pdf_to_images_and_text(pdf3: Path):
    images = get("pdf.png")([pdf3])
    assert len(images) == 3 and all(Image.open(i).width > 1000 for i in images)
    (txt,) = get("pdf.text")([pdf3])
    assert "Page 2 of the Spicchio report" in txt.read_text(encoding="utf-8")


def test_pdf_compress_produces_a_valid_pdf(pdf3: Path):
    (out,) = get("pdf.compress")([pdf3])
    assert len(PdfReader(out).pages) == 3


# --- data and generic ----------------------------------------------------

def test_csv_json_round_trip_with_semicolons_and_accents(tmp_path: Path):
    src = tmp_path / "guests.csv"
    src.write_text("name;city\nNicolò;Milano\nAnna;Zürich\n", encoding="utf-8")
    (js,) = get("data.json")([src])
    rows = json.loads(js.read_text(encoding="utf-8"))
    assert rows == [{"name": "Nicolò", "city": "Milano"}, {"name": "Anna", "city": "Zürich"}]
    (back,) = get("data.csv")([js])
    assert back.read_text(encoding="utf-8-sig").splitlines()[1] == "Nicolò,Milano"


def test_json_that_is_not_a_table(tmp_path: Path):
    src = tmp_path / "x.json"
    src.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ActionError, match="list of objects"):
        get("data.csv")([src])


def test_zip_several_files(photo: Path, pdf3: Path):
    (z,) = get("any.zip")([photo, pdf3])
    assert z.name == "photo-and-1-more.zip"
    assert sorted(zipfile.ZipFile(z).namelist()) == ["photo.jpg", "report.pdf"]


def test_checksum(photo: Path):
    import hashlib

    (out,) = get("any.sha256")([photo])
    assert out.read_text().split()[0] == hashlib.sha256(photo.read_bytes()).hexdigest()


# --- media (only where ffmpeg is installed) ------------------------------

@pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not installed")
def test_video_actions(tmp_path: Path):
    import subprocess

    from spicchio.actions.media import ffmpeg

    src = tmp_path / "clip.mov"
    subprocess.run([ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:v", "mpeg4", "-c:a", "aac",
                    str(src)], check=True)
    assert [a.id for a in actions_for([src], "convert")][:3] == ["video.mp4", "video.gif", "media.mp3"]
    assert [a.id for a in actions_for([src], "tools")] == ["video.compress", "video.email", "video.frame", "video.mute"]
    for action in ("video.mp4", "video.gif", "media.mp3", "video.frame", "video.email"):
        (out,) = get(action)([src])
        assert out.exists() and out.stat().st_size > 0


# --- command line --------------------------------------------------------

def test_cli_run_and_list(photo: Path, capsys):
    assert cli(["list", str(photo)]) == 0
    assert "img.pdf" in capsys.readouterr().out
    assert cli(["run", "img.pdf", str(photo)]) == 0
    assert capsys.readouterr().out.strip().endswith("photo.pdf")
    assert cli(["run", "pdf.split", str(photo)]) == 2


def test_ico_has_every_size(photo: Path):
    (out,) = get("img.ico")([photo])
    assert out.suffix == ".ico"
    assert Image.open(out).size[0] == Image.open(out).size[1]


def test_email_size_fits_under_one_megabyte(tmp_path: Path):
    src = tmp_path / "huge.png"
    Image.effect_noise((2600, 1800), 90).convert("RGB").save(src)
    assert src.stat().st_size > 1_000_000
    (out,) = get("img.email")([src])
    assert out.name == "huge-email.jpg" and out.stat().st_size <= 1_000_000


def test_copy_path_returns_text_for_the_clipboard(photo: Path, pdf3: Path):
    result = get("any.path")([photo, pdf3])
    assert isinstance(result, Done)
    assert result.clipboard == f"{photo}\n{pdf3}"
    assert result.message == "2 paths copied"


def test_undo_trashes_outputs_and_empty_folders_but_never_sources(pdf3: Path):
    from spicchio.undo import undo

    outs = get("pdf.split")([pdf3])
    trashed = []

    def fake_trash(p: Path):
        trashed.append(p)
        if p.is_dir():
            p.rmdir()
        else:
            p.unlink()

    assert undo(outs + [pdf3], [pdf3], trash=fake_trash) == 3
    assert pdf3.exists()
    assert trashed[-1].name == "report-pages" and not trashed[-1].exists()
