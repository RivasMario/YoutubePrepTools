# YouTube Prep Tools

A self-hosted web app for prepping YouTube videos: cuts silence and exports an EDL for your editor (DaVinci, Kdenlive, etc.), and transcribes audio with Whisper for subtitles or chapter notes.

Originally a Tkinter desktop tool by [RavinMaddHatter](https://github.com/RavinMaddHatter/YoutubePrepTools); this fork is a containerized Streamlit web app you can run on a home server (TrueNAS, Proxmox, any Docker host) and access from a browser.

## What it does

- **Silence cutter** — Analyzes audio levels per channel, removes silent gaps, and exports a `.edl` you can drop straight into your NLE timeline.
- **Whisper transcriber** — Transcribes audio with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2 backend, runs on CPU). Supports `tiny`, `base`, `small`, `medium`, `large-v3`.
- **Audio preprocessing** — Optional ffmpeg pipeline (highpass + loudnorm, optional aggressive denoise) for rough source recordings.
- **Combined folder transcripts** — Stitch all transcripts in a folder into one file with optional chapter headers per source clip.
- **Server-side file access** — Point it at a mounted `/data` directory; no need to upload multi-GB files through the browser.
- **Browser uploads** — Up to 4 GB per file for smaller clips.

## Quick start (Docker)

Pull and run from GitHub Container Registry:

```bash
docker run -d --name yptools --restart unless-stopped \
  -p 8501:8501 \
  -v /path/to/your/videos:/data \
  ghcr.io/rivasmario/youtubepreptools:latest
```

Then open <http://localhost:8501>. Your videos will appear at `/data/...` inside the app.

## Deploying on a home server

### TrueNAS SCALE
1. Apps → Discover → **Custom App**
2. Image: `ghcr.io/rivasmario/youtubepreptools:latest`
3. Port mapping: container `8501` → host `8501`
4. Storage: host path of your video dataset → container path `/data`
5. Save and start, then browse to `http://<truenas-ip>:8501`

### Proxmox
Run inside an LXC or VM with Docker installed:
```bash
docker run -d --name yptools --restart unless-stopped \
  -p 8501:8501 -v /path/to/videos:/data \
  ghcr.io/rivasmario/youtubepreptools:latest
```

### Mounting a remote SMB/NFS share into the container
On a Linux Docker host (e.g. via Tailscale to your NAS):
```bash
sudo mount -t cifs //192.168.0.203/winset /mnt/winset -o username=nasuser
docker run -d --name yptools -p 8501:8501 -v /mnt/winset:/data \
  ghcr.io/rivasmario/youtubepreptools:latest
```

## Using the app

### Sidebar settings
- **Audio Thresholds (dB)** — enable channels and set the silent-cutoff level per channel.
- **Timing Rules** — lead-in, lead-out, minimum clip length, minimum silent duration.
- **Whisper Model** — pick model size. `large-v3` is best quality but slowest.
- **Audio Preprocessing**
  - *Normalize + clean audio* — safe for almost everything; fixes loudness and rumble.
  - *Aggressive denoise* — only for muffled/noisy recordings; can hurt clean audio.
- **Folder Transcription**
  - *Combine into one file* — stitches all clip transcripts into a single file at the folder level.
  - *Add chapter headers* — inserts `## filename` markers between sections.

### Workflow
1. Set your audio thresholds and timing rules in the sidebar.
2. **Video Cutter** tab: enter a server path (e.g. `/data/my-project/`) or upload files.
3. Click **Cut Single Clip (EDL)** or **Cut Folder (Merge to EDL)** → download the `.edl`.
4. Import the EDL into DaVinci Resolve, Kdenlive, or any NLE that reads CMX3600.
5. **Audio Transcriber** section: pick a model and transcribe a single file or a whole folder.

## Building from source

```bash
git clone https://github.com/RivasMario/YoutubePrepTools.git
cd YoutubePrepTools
docker build -t youtubepreptools:latest .
docker run -d -p 8501:8501 -v /path/to/videos:/data youtubepreptools:latest
```

### Local dev (no Docker)
Requires Python 3.11+ and `ffmpeg` on the host.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Project layout

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit web UI |
| `cutter.py` | Silence-detection and EDL generation |
| `openai_translator.py` | Whisper transcription wrapper (faster-whisper) |
| `access_ffprobe.py` | ffprobe metadata parser |
| `aws_translator.py` | AWS Translate helper (optional) |
| `youtubePrep.py` | Legacy Tkinter desktop entrypoint (kept for reference) |
| `Dockerfile` | Container image definition |
| `init.sh` | Container entrypoint (starts Streamlit) |
| `requirements.txt` | Python dependencies |
| `youtubeDescription.json` | Saved settings + boilerplate description text |

## Credits

Original project: [RavinMaddHatter/YoutubePrepTools](https://github.com/RavinMaddHatter/YoutubePrepTools)

- [Discord](https://discord.com/invite/M7MHtUab2r)
- [YouTube](https://www.youtube.com/channel/UCKHWmRRTGUc0Ssgd3SarD5g)
- [ko-fi](https://ko-fi.com/ravinmaddhatter) — tip the original developer
