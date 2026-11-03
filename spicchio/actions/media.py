"""Video and audio actions. They need ffmpeg on PATH; without it the slices simply don't appear."""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from spicchio.actions.base import Action, ActionError, each, register
from spicchio.files import Kind, output_path
from spicchio.safety import find_program

VIDEO = frozenset({Kind.VIDEO})
AUDIO = frozenset({Kind.AUDIO})
MEDIA = VIDEO | AUDIO


@lru_cache(maxsize=1)
def ffmpeg() -> str | None:
    return find_program("ffmpeg")


def has_ffmpeg() -> bool:
    return ffmpeg() is not None


# No console window flashing on Windows while ffmpeg runs.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _exe() -> str:
    exe = ffmpeg()
    if exe is None:
        raise ActionError("ffmpeg is not installed")
    return exe


# A media file can be a playlist in disguise that asks ffmpeg to read other files or
# go online. Inputs are opened as plain local files, by these demuxers only.
_FORMATS = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,avi,mp3,wav,flac,ogg,aac,mpegts,asf,flv,aiff"
_SAFE_INPUT = ("-protocol_whitelist", "file", "-format_whitelist", _FORMATS)


def _url(path: Path) -> str:
    """``file:`` + absolute path: a name like ``-y.mp4`` or ``http:x.mp4`` stays a file name."""
    return "file:" + str(path.resolve())


def _ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([_exe(), "-hide_banner", "-nostdin", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=_NO_WINDOW, check=False)


def _run(args: list[str], source: Path, out: Path, before_input: tuple[str, ...] = ()) -> None:
    proc = _ffmpeg(["-loglevel", "error", "-n", *before_input, *_SAFE_INPUT, "-i", _url(source), *args, _url(out)])
    if proc.returncode != 0:
        if out.is_file() and not out.is_symlink():
            out.unlink()  # no half-written file left behind
        last = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise ActionError(f"ffmpeg failed on {source.name}: {last}")


def to_mp4(path: Path) -> Path:
    out = output_path(path, ".mp4")
    _run(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"], path, out)
    return out


def compress_video(path: Path) -> Path:
    out = output_path(path, ".mp4", "compressed")
    _run(["-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"], path, out)
    return out


def to_gif(path: Path) -> Path:
    """First 10 seconds, 480 px wide, 12 fps, with a proper palette so it doesn't look banded."""
    out = output_path(path, ".gif")
    graph = ("fps=12,scale=480:-1:flags=lanczos,split[a][b];"
             "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    _run(["-t", "10", "-vf", graph], path, out)
    return out


def mute(path: Path) -> Path:
    out = output_path(path, path.suffix.lower(), "muted")
    _run(["-c:v", "copy", "-an"], path, out)
    return out


def to_mp3(path: Path) -> Path:
    out = output_path(path, ".mp3")
    _run(["-vn", "-c:a", "libmp3lame", "-q:a", "2"], path, out)
    return out


def to_wav(path: Path) -> Path:
    out = output_path(path, ".wav")
    _run(["-vn", "-c:a", "pcm_s16le"], path, out)
    return out


def duration(path: Path) -> float:
    """Length in seconds, read from ffmpeg's own report (no ffprobe needed)."""
    proc = _ffmpeg([*_SAFE_INPUT, "-i", _url(path)])
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
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", str(audio), "-movflags", "+faststart"], path, out)
    return out


def snapshot(path: Path) -> Path:
    """A PNG of the frame in the middle of the video."""
    out = output_path(path, ".png", "frame")
    _run(["-frames:v", "1"], path, out, before_input=("-ss", f"{duration(path) / 2:.2f}"))
    return out


def to_m4a(path: Path) -> Path:
    out = output_path(path, ".m4a")
    _run(["-vn", "-c:a", "aac", "-b:a", "192k"], path, out)
    return out


def to_flac(path: Path) -> Path:
    out = output_path(path, ".flac")
    _run(["-vn", "-c:a", "flac"], path, out)
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
