"""Video and audio actions. They need ffmpeg on PATH; without it the slices simply don't appear."""

from __future__ import annotations

import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from spicchio.actions.base import Action, ActionError, each, register
from spicchio.files import Kind, output_path

VIDEO = frozenset({Kind.VIDEO})
AUDIO = frozenset({Kind.AUDIO})
MEDIA = VIDEO | AUDIO


@lru_cache(maxsize=1)
def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def has_ffmpeg() -> bool:
    return ffmpeg() is not None


def _run(args: list[str], source: Path) -> None:
    exe = ffmpeg()
    if exe is None:
        raise ActionError("ffmpeg is not installed")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # no console flashing on Windows
    proc = subprocess.run(
        [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), *args],
        capture_output=True,
        text=True,
        creationflags=flags,
    )
    if proc.returncode != 0:
        last = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise ActionError(f"ffmpeg failed on {source.name}: {last}")


def to_mp4(path: Path) -> Path:
    out = output_path(path, ".mp4")
    _run(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], path)
    return out


def compress_video(path: Path) -> Path:
    out = output_path(path, ".mp4", "compressed")
    _run(["-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], path)
    return out


def to_gif(path: Path) -> Path:
    """First 10 seconds, 480 px wide, 12 fps, with a proper palette so it doesn't look banded."""
    out = output_path(path, ".gif")
    graph = ("fps=12,scale=480:-1:flags=lanczos,split[a][b];"
             "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    _run(["-t", "10", "-vf", graph, str(out)], path)
    return out


def mute(path: Path) -> Path:
    out = output_path(path, path.suffix.lower(), "muted")
    _run(["-c:v", "copy", "-an", str(out)], path)
    return out


def to_mp3(path: Path) -> Path:
    out = output_path(path, ".mp3")
    _run(["-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out)], path)
    return out


def to_wav(path: Path) -> Path:
    out = output_path(path, ".wav")
    _run(["-vn", "-c:a", "pcm_s16le", str(out)], path)
    return out


register(Action("video.mp4", "MP4", VIDEO, each(to_mp4), skip_ext=frozenset({".mp4"}), available=has_ffmpeg))
register(Action("video.compress", "Compress", VIDEO, each(compress_video), available=has_ffmpeg))
register(Action("video.gif", "GIF", VIDEO, each(to_gif), available=has_ffmpeg))
register(Action("video.mute", "Mute", VIDEO, each(mute), available=has_ffmpeg))
register(Action("media.mp3", "MP3", MEDIA, each(to_mp3), skip_ext=frozenset({".mp3"}), available=has_ffmpeg))
register(Action("audio.wav", "WAV", AUDIO, each(to_wav), skip_ext=frozenset({".wav"}), available=has_ffmpeg))
