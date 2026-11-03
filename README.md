<p align="center">
  <img src="assets/spicchio.png" width="84" alt="Spicchio: a tangerine in section, one slice lifted out">
</p>

<h1 align="center">Spicchio</h1>

<p align="center">
  <b>Drag a file. Press Shift. Drop it on a slice.</b><br>
  Convert, compress and transform files from a radial menu that opens under your cursor.<br>
  No app to open, no upload, no account.
</p>

<p align="center">
  <a href="https://github.com/GiovanniBishara/Spicchio/releases/latest"><b>⬇ Download for Windows or macOS</b></a>
  &nbsp;·&nbsp;
  <a href="#how-to-use">How to use</a>
  &nbsp;·&nbsp;
  <a href="#what-it-can-do">What it can do</a>
</p>

<p align="center">
  <a href="https://github.com/GiovanniBishara/Spicchio/actions/workflows/ci.yml"><img src="https://github.com/GiovanniBishara/Spicchio/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-ff6a24" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-Windows%20%C2%B7%20macOS%20(beta)-1c1b21" alt="Windows and macOS (beta)">
  <img src="https://img.shields.io/badge/license-MIT-1c1b21" alt="MIT">
</p>

<p align="center">
  <img src="docs/wheel-render.png" width="460" alt="The Spicchio wheel: an image is being dropped on the PDF pill, and 'Convert to PDF' is written in the middle">
</p>

*Spicchio* is Italian for a slice of a tangerine.

## Try it in one minute

**Windows 10/11**
1. Download **Spicchio-windows.zip** from the [latest release](https://github.com/GiovanniBishara/Spicchio/releases/latest) and unzip it.
2. Double-click **Spicchio.exe**. If Windows says *"Windows protected your PC"*, click **More info → Run anyway** (the app is not signed, that's all).
3. A tangerine appears in the tray, bottom right (it may be hidden under the **^** arrow). Spicchio is ready.

**macOS** *(experimental)*
1. Download **Spicchio-macOS.zip**, unzip it and move **Spicchio.app** to Applications.
2. Right-click the app → **Open** → **Open** (needed once, the app is not notarised).
3. Allow Spicchio in **System Settings → Privacy & Security → Accessibility** and **Input Monitoring**, then open it again. The tangerine appears in the menu bar.

## How to use

1. **Start dragging a file** (or several) from Explorer, Finder or the desktop. Keep the mouse button down.
2. **Tap Shift.** The wheel opens under the cursor with only the actions that make sense for those files.
3. **Move towards an action.** You choose by direction: you can go past the circle, the pill lights up and its full name appears in the middle.
4. **Let go.** The result is saved **next to the original**, which is never changed or overwritten (`photo.pdf`, then `photo (1).pdf`...). A notification tells you what was created: click it to see the file.

To cancel, drop in the middle or press **Esc**.

**A few things to try**
- Drag two or three photos together → **PDF**: one PDF with one page per photo.
- Drag two PDFs → **Merge**.
- Drag a phone photo → **No metadata**: the copy has no GPS position or camera details.
- Drag a screen recording → **GIF** (needs ffmpeg, see below).

**The tray menu** (right-click the tangerine) lets you pause Spicchio, start it with Windows, see these instructions again, or quit.

## What it can do

| Files | Actions |
| --- | --- |
| **Images** (PNG, JPG, WebP, GIF, BMP, TIFF) | PDF (several images become one PDF), PNG, JPG, WebP, Compress, Half size, Remove metadata (EXIF, GPS) |
| **PDF** | Merge (two or more), Images (one PNG per page), Compress, Split pages, Rotate, Extract text |
| **Video** (MP4, MOV, MKV, WebM, AVI) | MP4 (H.264), Compress, GIF, Mute, MP3 |
| **Audio** (MP3, WAV, M4A, OGG, FLAC) | MP3, WAV |
| **Data** | CSV → JSON (detects `;` and tabs), JSON → CSV (opens correctly in Excel) |
| **Anything** | ZIP, SHA-256 checksum |

Video and audio actions appear only if [ffmpeg](https://ffmpeg.org) is installed: `winget install ffmpeg` on Windows, `brew install ffmpeg` on macOS. Everything runs **offline** on your computer.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The wheel opens but won't take the file | Don't run Spicchio *as administrator*: Windows blocks drops from Explorer into elevated apps. |
| Nothing happens when I press Shift | Press Shift *while* the file is already moving, not before. Check that Spicchio is enabled in the tray menu. |
| No video or audio actions | Install ffmpeg (see above) and restart Spicchio. |
| macOS: nothing happens | Give Accessibility and Input Monitoring permission, then quit and reopen Spicchio. |

## Run from source

```powershell
git clone https://github.com/GiovanniBishara/Spicchio.git
cd Spicchio
python -m venv .venv
.venv\Scripts\activate          # macOS: source .venv/bin/activate
pip install -e .
spicchio                        # Ctrl+C or the tray menu to quit
```

Every action also works from the terminal, which is handy for scripts:

```powershell
spicchio actions                      # every action
spicchio list report.pdf              # what the wheel would show for this file
spicchio run pdf.split report.pdf     # report-pages\report-1.pdf, report-2.pdf, ...
spicchio run img.pdf a.jpg b.png      # a-album.pdf
```

## Under the hood

```
spicchio/
├── trigger.py      when to open: a tiny state machine fed by global mouse/keyboard hooks (pynput)
├── geometry.py     pure maths of the wheel: which action lies in the pointer's direction
├── files.py        file kinds and collision-free output paths
├── actions/        one module per family; each action declares which files it accepts
│   ├── base.py     Action model and registry
│   ├── images.py   Pillow
│   ├── pdf.py      pypdf, pypdfium2
│   ├── media.py    ffmpeg
│   └── data.py     csv/json, zip, sha256
├── ui/
│   ├── wheel.py    transparent always-on-top Qt window that accepts the drop
│   ├── style.py    the visual language: warm ink, warm white, one tangerine accent
│   ├── icon.py     the mark, drawn in code
│   ├── toast.py    the notification
│   └── dragimage.py hides the shell's big drag preview while you're on the wheel (Windows)
├── app.py          tray app, wiring and worker thread
└── cli.py          the same actions from the command line
```

A few decisions worth mentioning:

- **The wheel is a real drop target.** The operating system does the drag and drop: Spicchio only shows a window under the cursor at the right moment and accepts the files, always as a *copy*, so the original is never moved or deleted.
- **Choosing by direction.** The pointer can travel past the circle, so the file preview drawn next to the cursor never hides the labels.
- **Logic is separated from the UI.** Trigger rules and wheel geometry are plain Python, unit tested without a mouse or a screen; the Qt wheel is rendered off-screen in CI.
- **Actions are data.** A new action is one function and one `register(Action(...))` line; the wheel picks it up for the right file types.
- **Work happens off the UI thread**, so a long video conversion never freezes the cursor.

## Development

```powershell
pip install -e ".[dev]"
pytest                          # actions on real files, geometry, trigger, CLI, off-screen wheel
ruff check .
python scripts/render_wheel.py renders   # PNG renders of the wheel, the notification and the icon
```

CI runs lint and tests on Windows, macOS and Linux, builds the Windows and macOS apps, and renders the design on Windows (see the `renders` branch). Publishing a release on GitHub attaches both apps to it automatically.

## Roadmap

- [ ] Office documents to PDF (Word, Excel, PowerPoint)
- [ ] OCR for scanned PDFs
- [ ] Background removal for images
- [ ] Settings to choose and reorder actions
- [ ] Signed builds

## Credits

Inspired by [Tangerine](https://www.digitaltrends.com/computing/tangerine-for-mac-makes-file-conversions-seamless-with-a-simple-drag-and-drop-gesture/), a macOS app built around the same gesture. Spicchio is an independent, open-source implementation.

Made by [Giovanni Bishara](https://www.linkedin.com/in/giovanni-bishara-912a63236). MIT licensed.
