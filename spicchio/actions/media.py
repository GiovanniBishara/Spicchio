"""Video and audio actions. They need ffmpeg on PATH; without it the slices simply don't appear."""

from __future__ import annotations

import re
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


def duration(path: Path) -> float:
    """Length in seconds, read from ffmpeg's own report (no ffprobe needed)."""
    exe = ffmpeg()
    if exe is None:
        raise ActionError("ffmpeg is not installed")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.run([exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True, creationflags=flags)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise ActionError(f"Can't read the length of {path.name}")
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


EMAIL_VIDEO_BYTES = 20_000_000


def email_video(path: Path) -> Path:
    """An MP4 under 20 MB: the video bitrate is computed from the length."""
    seconds = max(duration(path), 1.0)
    audio = 96_000
    video = int(EMAIL_VIDEO_BYTES * 8 * 0.94 / seconds) - audio
    if video < 150_000:
        raise ActionError(f"{path.name} is too long to fit in 20 MB")
    out = output_path(path, ".mp4", "email")
    width = 1280 if video > 1_500_000 else 854 if video > 600_000 else 640
    _run(["-vf", f"scale='min({width},iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
          "-b:v", str(video), "-maxrate", str(int(video * 1.3)), "-bufsize", str(video * 2),
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", str(audio), "-movflags", "+faststart", str(out)], path)
    return out


def snapshot(path: Path) -> Path:
    """A PNG of the frame in the middle of the video."""
    middle = duration(path) / 2
    out = output_path(path, ".png", "frame")
    exe = ffmpeg()
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{middle:.2f}", "-i", str(path),
                           "-frames:v", "1", str(out)], capture_output=True, text=True, creationflags=flags)
    if proc.returncode != 0 or not out.exists():
        raise ActionError(f"Can't take a frame from {path.name}")
    return out


def to_m4a(path: Path) -> Path:
    out = output_path(path, ".m4a")
    _run(["-vn", "-c:a", "aac", "-b:a", "192k", str(out)], path)
    return out


def to_flac(path: Path) -> Path:
    out = output_path(path, ".flac")
    _run(["-vn", "-c:a", "flac", str(out)], path)
    return out


FF = has_ffmpeg
register(Action("video.mp4", "MP4", VIDEO, each(to_mp4), skip_ext=frozenset({".mp4"}), available=FF, title="Convert to MP4"))
register(Action("video.gif", "GIF", VIDEO, each(to_gif), available=FF, title="First 10 s as GIF"))
register(Action("media.mp3", "MP3", MEDIA, each(to_mp3), skip_ext=frozenset({".mp3"}), available=FF, title="Extract MP3"))
register(Action("audio.m4a", "M4A", AUDIO, each(to_m4a), skip_ext=frozenset({".m4a"}), available=FF, title="Convert to M4A"))
register(Action("audio.wav", "WAV", AUDIO, each(to_wav), skip_ext=frozenset({".wav"}), available=FF, title="Convert to WAV"))
register(Action("audio.flac", "FLAC", AUDIO, each(to_flac), skip_ext=frozenset({".flac"}), available=FF, title="Lossless FLAC"))
register(Action("video.compress", "Compress", VIDEO, each(compress_video), available=FF, title="Make it smaller", side="tools"))
register(Action("video.email", "Under 20 MB", VIDEO, each(email_video), available=FF, title="Ready for email", side="tools"))
register(Action("video.frame", "Snapshot", VIDEO, each(snapshot), available=FF, title="Middle frame as PNG", side="tools"))
register(Action("video.mute", "Mute", VIDEO, each(mute), available=FF, title="Remove the audio", side="tools"))
