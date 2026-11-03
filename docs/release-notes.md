**Drag a file. Press Shift. Drop it on a slice.**

![Spicchio demo](https://raw.githubusercontent.com/GiovanniBishara/Spicchio/main/docs/demo.gif)

The first release of Spicchio: a ring of tangerine slices that opens under your cursor while you drag a file.

- **Images** (including iPhone HEIC): PDF, JPG, PNG, WebP, ICO · Compress, **Under 1 MB**, Half size, Remove metadata
- **PDF**: pages to images, text · Merge, Compress, Split pages, Rotate
- **Video and audio** (with ffmpeg): MP4, GIF, MP3, M4A, WAV, FLAC · Compress, **Under 20 MB**, Snapshot, Mute
- **Data**: CSV ↔ JSON · **Any file or folder**: ZIP, Copy path, Terminal here, SHA-256
- Three sides on the wheel (**Convert, Tools, Actions**): tap Shift again to turn it
- The original is never touched; **Undo** sends results to the Recycle Bin
- Offline, and hardened against hostile files: see [SECURITY.md](https://github.com/GiovanniBishara/Spicchio/blob/main/SECURITY.md)

### Download

| | |
| --- | --- |
| **Windows 10/11** | `Spicchio-windows.zip` → unzip → double-click `Spicchio.exe` |
| **macOS** (experimental) | `Spicchio-macOS.zip` → unzip → right-click `Spicchio.app` → Open |

The apps are attached a few minutes after publishing, built by GitHub Actions from this exact source. `SHA256SUMS.txt` lets you verify them (`Get-FileHash Spicchio-windows.zip` on Windows).

Windows may show "Windows protected your PC" because the app is not signed: click **More info → Run anyway**.
On macOS, allow Spicchio in **System Settings → Privacy & Security → Accessibility** and **Input Monitoring**, then open it again.

See the [README](https://github.com/GiovanniBishara/Spicchio#readme) for every action and for troubleshooting.
