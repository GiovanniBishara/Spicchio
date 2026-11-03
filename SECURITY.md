# Security

Spicchio runs on your computer, with your permissions, on files that often come
from somewhere else: a download, an email attachment, a chat. This page says
what it does to stay safe, what it can't promise, and how to report a problem.

## What Spicchio does and doesn't do

- **No network.** Spicchio never connects to the internet: no updates, no
  telemetry, no accounts. Files never leave your computer.
- **Keyboard and mouse.** To know when to open the wheel it listens for Shift,
  Tab, Esc, the left button and the pointer position. Every other key is ignored
  on arrival: nothing is stored, logged or sent.
- **Your files.** The original is only ever read. Results are new files next to
  it; an existing file is never overwritten. Undo sends results to the Recycle
  Bin, never the originals, and leaves alone a result you edited afterwards.

## Untrusted files

Every dropped file is treated as hostile until proven otherwise.

| Risk | What Spicchio does |
| --- | --- |
| **Decompression bombs** (a tiny image that claims to be gigapixels) | Images over 120 megapixels are refused before decoding. PDF pages are rendered within a 40-megapixel budget, whatever size they claim. CSV/JSON over 200 MB are refused; deeply nested JSON fails cleanly. |
| **Media files that are playlists in disguise** (they can make ffmpeg read other files or go online) | ffmpeg may only open plain local files (`-protocol_whitelist file`) with a short list of real audio/video demuxers (`-format_whitelist`). Playlists, `concat` and network protocols are refused. |
| **File names that look like options** (`-y.mp4`, `http:x.mp4`) | Paths are given to ffmpeg as `file:` + absolute path, and ffmpeg runs with `-n` (never overwrite) and `-nostdin`. |
| **Formulas in data** (`=HYPERLINK(...)` in someone's JSON, opened in Excel) | JSON → CSV writes cells that start with `=`, `+`, `-`, `@` as text (`'=...`). Plain numbers like `-5` are kept. |
| **Symbolic links** | A result is never written through a link, not even a dangling one. When you zip a folder, links inside it that point to other places in the same folder are packed normally; a link that points *outside* the folder (say, to `~/.ssh`) is left out and the notification says so by name, so a folder you got from someone can't quietly pack your own files. |
| **A planted program** (a fake `ffmpeg.exe` in Downloads) | External programs are looked up by absolute path only, never in the current folder; Windows tools (Explorer, PowerShell) by their full system path. Nothing runs through a shell, and a file or folder name is always a separate argument. |
| **Bugs in the file libraries** (Pillow, pypdf, PDFium, libheif, ffmpeg) | Minimum versions include the known fixes; CI runs `pip-audit` on every change and Dependabot proposes updates every week. ffmpeg is your own install: keep it updated (`winget upgrade ffmpeg`, `brew upgrade ffmpeg`). |

## Downloads

- The apps are built by GitHub Actions from the tagged source, never on a
  personal machine. The build log of every release is public.
- Each release has a `SHA256SUMS.txt`. To check a download:
  - Windows (PowerShell): `Get-FileHash Spicchio-windows.zip`
  - macOS: `shasum -a 256 Spicchio-macOS.zip`

  and compare with the line in `SHA256SUMS.txt`.
- Workflows use a read-only token by default; only the step that attaches files
  to a release can write. Third-party actions are pinned to exact commits.
- The builds are not code-signed yet, which is why Windows SmartScreen and
  macOS Gatekeeper ask for confirmation the first time.

## Reporting a vulnerability

Please don't open a public issue. Use **Security → Report a vulnerability** on
this repository (private to the maintainer), with the file or steps that
reproduce it. You'll get an answer within a week.

Only the latest release is supported.
