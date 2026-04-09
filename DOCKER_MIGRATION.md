# YoutubePrepTools Docker & Web App Migration

## Why We Containerized the App
The original application was a desktop GUI built with `Tkinter`. To use this application on a headless home server (like TrueNAS or Proxmox) and access it remotely, it needed to be converted into a web application.

## Key Changes & Fixes

1. **Streamlit Web UI (`app.py`)**
   - Replaced the Tkinter interface with a modern web UI using Streamlit.
   - Instead of uploading massive video files through the browser (which would crash or take hours), the app is designed to read files directly from the server's hard drive by pointing it to a `/data/` mount.
   - Added an upload tab (configured for up to 4GB files) for smaller files.
   - Added immediate "Download" buttons for the generated `.edl` and `.txt` files upon task completion.

2. **Expanded File Format Support**
   - The original code hardcoded searches for `.mkv` files.
   - Updated the `glob` logic in both the "Cut Folder" and "Transcribe Folder" functions to support `.mp4`, `.mov`, `.avi`, `.wav`, and `.mkv` files (and their uppercase variants).

3. **FFmpeg & Audio Stream Bug (`cutter.py`)**
   - **The Problem:** The original code extracted audio using `ffmpeg -map 0:1`. This assumes that the audio stream is *always* the second stream in the file (index 1). In many `.mp4` files, the audio is actually index 0. This caused ffmpeg to crash when trying to convert a video stream into a `.wav` file.
   - **The Fix:** Changed the map argument to `-map 0:a:{chan-1}`. The `a:` specifier tells ffmpeg to specifically target the *audio* streams, completely ignoring the video streams regardless of their absolute index.

4. **FFprobe Subprocess Bug (`access_ffprobe.py`)**
   - **The Problem:** The `subprocess.check_output(cmd, shell=True)` call was failing because `cmd` was passed as a Python list. When `shell=True` is used, the command should be a single string.
   - **The Fix:** Changed it to `shell=False` so the list of arguments is executed safely and correctly.

## Deployment on TrueNAS (via Fedora / Tailscale)
To process files that live on a TrueNAS server without moving them to the laptop:
1. The TrueNAS SMB share is mounted to the host machine (Fedora) at the system level:
   `sudo mount -t cifs //192.168.0.203/winset /mnt/winset -o username=nasuser`
2. The Docker container is launched with `/mnt/winset` volume-mounted to `/data`:
   `sudo docker run -d --name yptools -p 8501:8501 -v /mnt/winset:/data youtubepreptools`
3. The web app is accessed at `http://localhost:8501`, and the server path is provided as `/data/VIDEO_CAPTURE_PROJECTS/...`.