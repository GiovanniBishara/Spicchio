"""Hostile inputs: files and folders crafted to make Spicchio do something it shouldn't."""

import os
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from spicchio.actions import ActionError, get
from spicchio.actions.data import safe_cell
from spicchio.actions.media import has_ffmpeg
from spicchio.files import output_path
from spicchio.safety import find_program

needs_links = pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need admin rights on Windows")


def _fake_program(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / (name + (".exe" if sys.platform == "win32" else ""))
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return exe


def test_programs_are_never_taken_from_the_current_folder(tmp_path, monkeypatch):
    planted = _fake_program(tmp_path / "downloads", "spicchio-probe")
    real = _fake_program(tmp_path / "bin", "spicchio-probe")
    monkeypatch.chdir(planted.parent)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(planted.parent), str(real.parent)]))
    assert find_program("spicchio-probe") == str(real)
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(planted.parent)]))
    assert find_program("spicchio-probe") is None


@needs_links
def test_output_never_writes_through_a_dangling_link(photo: Path, tmp_path: Path):
    target = tmp_path / "elsewhere" / "victim.txt"
    (photo.parent / "photo.png").symlink_to(target)
    out = output_path(photo, ".png")
    assert out.name == "photo (1).png"
    get("img.png")([photo])
    assert not target.exists()


@needs_links
def test_zip_leaves_out_links_to_the_rest_of_the_disk(tmp_path: Path):
    secret = tmp_path / "secret" / "id_ed25519"
    secret.parent.mkdir()
    secret.write_text("PRIVATE KEY")
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello")
    (folder / "key").symlink_to(secret)
    (folder / "loop").symlink_to(folder, target_is_directory=True)
    (z,) = get("any.zip")([folder])
    assert zipfile.ZipFile(z).namelist() == ["project/notes.txt"]


def test_spreadsheet_formulas_arrive_as_text(tmp_path: Path):
    assert safe_cell("=HYPERLINK(\"http://x\",\"click\")").startswith("'=")
    assert safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert safe_cell("-5") == "-5" and safe_cell("+3.2") == "+3.2" and safe_cell(7) == 7
    src = tmp_path / "people.json"
    src.write_text('[{"name": "=cmd|\' /C calc\'!A0", "age": -4}]', encoding="utf-8")
    (out,) = get("data.csv")([src])
    row = out.read_text(encoding="utf-8-sig").splitlines()[1]
    assert row.startswith("'=cmd") and row.endswith(",-4")


def test_deeply_nested_json_is_refused_cleanly(tmp_path: Path):
    src = tmp_path / "deep.json"
    src.write_text("[" * 200_000 + "]" * 200_000)
    with pytest.raises(ActionError):
        get("data.csv")([src])


def test_decompression_bomb_is_refused(photo: Path, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # the photo is 64x48: "too big" here
    with pytest.raises(ActionError, match="too large"):
        get("img.png")([photo])


def test_huge_pdf_pages_render_within_a_pixel_budget(pdf3: Path, monkeypatch):
    import spicchio.actions.pdf as pdf

    monkeypatch.setattr(pdf, "RENDER_PIXELS", 200_000)
    images = get("pdf.png")([pdf3])
    w, h = Image.open(images[0]).size
    assert w * h <= 200_000 * 1.02


def test_undo_keeps_a_result_you_edited_since(photo: Path):
    from spicchio.undo import stamps, undo

    (out,) = get("img.png")([photo])
    written = stamps([out])
    out.write_bytes(out.read_bytes() + b"edited")
    trashed = []
    assert undo([out], [photo], trash=trashed.append, written=written) == 0
    assert not trashed


@pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not installed")
def test_a_playlist_disguised_as_a_video_cannot_read_other_files(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("do not leak")
    trap = tmp_path / "holiday.mp4"
    trap.write_text(f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:1.0,\nfile://{secret}\n#EXT-X-ENDLIST\n")
    with pytest.raises(ActionError):
        get("video.gif")([trap])
    assert not (tmp_path / "holiday.gif").exists()  # nothing half-written left behind


@pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not installed")
def test_file_names_that_look_like_options_stay_file_names(tmp_path: Path):
    import subprocess

    from spicchio.actions.media import ffmpeg

    src = tmp_path / "-y.mov"
    subprocess.run([ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
                    "-c:v", "mpeg4", "file:" + str(src)], check=True)
    (out,) = get("video.frame")([src])
    assert out.name == "-y-frame.png" and out.stat().st_size > 0
