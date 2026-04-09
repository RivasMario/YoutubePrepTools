import streamlit as st
import time
import os
import json
from queue import Queue
from threading import Thread
from pathlib import Path
from glob import glob
from os.path import exists, split, join, getmtime
import cutter
import openai_translator as Translator

st.set_page_config(page_title="YouTube Prep Tools", layout="wide")

st.title("📹 YouTube Video Publishing Tools")
st.markdown("Automate video silence cutting, whisper translation, and description generation on your home server.")

# ----------------- Settings & Config -----------------
st.sidebar.header("Processing Settings")

confFile = "youtubeDescription.json"

def load_settings():
    if exists(confFile):
        with open(confFile) as file:
            return json.load(file)
    return {
        "model": "base", "in_space": 0.1, "out_space": 0.1, 
        "min_clip": 1.0, "min_silent": 0.1, 
        "sliders_enabled": [True, False, False, False, False, False],
        "slider_defaults": [-24, -24, -24, -24, -24, -24]
    }

def save_settings(data):
    with open(confFile, "w+") as file:
        json.dump(data, file, indent=2)

data = load_settings()

with st.sidebar.expander("Audio Thresholds (Db)"):
    sliders_enabled = []
    slider_defaults = []
    for i in range(6):
        col1, col2 = st.columns([1, 4])
        with col1:
            en = st.checkbox(f"Ch {i+1}", value=data["sliders_enabled"][i])
            sliders_enabled.append(en)
        with col2:
            val = st.slider(f"Level {i+1}", min_value=-60, max_value=0, value=data["slider_defaults"][i], key=f"sl_{i}")
            slider_defaults.append(val)

with st.sidebar.expander("Timing Rules (Seconds)"):
    in_space = st.number_input("In Space (Lead In)", value=data.get("in_space", 0.1))
    out_space = st.number_input("Out Space (Lead Out)", value=data.get("out_space", 0.1))
    min_clip = st.number_input("Min Clip Length", value=data.get("min_clip", 1.0))
    min_silent = st.number_input("Min Silent Duration", value=data.get("min_silent", 0.1))

selected_model = st.sidebar.selectbox("Whisper Model", ["tiny", "base", "small", "medium", "large-v3"], index=["tiny", "base", "small", "medium", "large-v3"].index(data.get("model", "base")) if data.get("model", "base") in ["tiny", "base", "small", "medium", "large-v3"] else 1)

st.sidebar.subheader("Audio Preprocessing")
preprocess_audio = st.sidebar.checkbox("Normalize + clean audio", value=False, help="Normalizes volume and removes rumble. Safe for most audio.")
denoise_audio = st.sidebar.checkbox("Aggressive denoise", value=False, help="Removes background noise. May strip detail from clean audio - only use for rough recordings.")

st.sidebar.subheader("Folder Transcription")
combine_transcripts = st.sidebar.checkbox("Combine into one file", value=True, help="Stitch all transcripts into a single file at the folder level.")
add_chapters = st.sidebar.checkbox("Add chapter headers", value=True, help="Insert a header per source file in the combined transcript.")

if st.sidebar.button("Save Settings"):
    data["model"] = selected_model
    data["in_space"] = in_space
    data["out_space"] = out_space
    data["min_clip"] = min_clip
    data["min_silent"] = min_silent
    data["sliders_enabled"] = sliders_enabled
    data["slider_defaults"] = slider_defaults
    save_settings(data)
    st.sidebar.success("Settings Saved!")

# ----------------- Video Processing -----------------
st.header("✂️ Video Cutter")
st.info("You can process files already on the server (e.g., in `/data`), or upload new ones.")

tab1, tab2 = st.tabs(["📁 Use Server Path", "☁️ Upload Files"])

with tab2:
    st.write("Upload files from your computer to the server's `/data/uploads` folder.")
    uploaded_files = st.file_uploader("Select Video/Audio Files", accept_multiple_files=True)
    if uploaded_files:
        if st.button("Save Uploads to Server"):
            upload_dir = "/data/uploads"
            os.makedirs(upload_dir, exist_ok=True)
            with st.spinner("Saving files to server... This might take a moment for large files."):
                for f in uploaded_files:
                    with open(os.path.join(upload_dir, f.name), "wb") as out_f:
                        out_f.write(f.read())
            st.success(f"✅ Saved {len(uploaded_files)} files to `{upload_dir}`. You can now process them from the 'Use Server Path' tab!")

with tab1:
    input_path = st.text_input("File or Folder Path (e.g., /data/my_video.mkv or /data/uploads/):", "/data/")

def do_settings(cc):
    levels = [-val for val in slider_defaults]
    cc.set_multi_chan_thres(levels)
    cc.set_lead_in(in_space)
    cc.set_lead_out(out_space)
    cc.set_min_clip_dur(min_clip)
    cc.set_enabled_tracks(sliders_enabled)
    cc.set_min_silent_dur(min_silent)

def run_task_with_progress(task_func, *args):
    q = Queue()
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # Run task in thread
    t = Thread(target=task_func, args=(q, *args))
    t.start()
    
    # Monitor queue
    complete = False
    output_file = None
    while not complete:
        time.sleep(0.1)
        if not q.empty():
            update = q.get()
            progress_bar.progress(int(update["percent"]) / 100)
            status_text.text(update["state"])
            if update["state"] == "done" or update["percent"] >= 100:
                complete = True
                if "Error" in update["state"]:
                    status_text.error(update["state"])
                else:
                    status_text.success("Task Complete!")
                progress_bar.progress(1.0)
                output_file = update.get("file", None)
                
    t.join()
    return output_file

def cut_clip_process(queue, video_file):
    name = Path(video_file).stem
    head, tail = split(video_file)
    cc = cutter.clipCutter(queue)
    try:
        do_settings(cc)
        cc.add_cut_video_to_timeline(video_file)
        cc.export_edl(join(head, name + "-cut.edl"))
        cc._cleanup()
        queue.put({"percent": 100, "state": "done", "file": join(head, name + "-cut.edl")})
    except Exception as e:
        queue.put({"percent": 100, "state": f"Error: {e}"})
        cc._cleanup()

def cut_folder_process(queue, folder):
    cc = cutter.clipCutter(queue)
    try:
        name = split(folder)[-1]
        do_settings(cc)
        files = []
        for ext in ("*.mkv", "*.mp4", "*.mov", "*.avi", "*.MKV", "*.MP4", "*.MOV", "*.AVI"):
            files.extend(glob(join(folder, ext)))
        files.sort(key=getmtime)
        for file in files:
            cc.add_cut_video_to_timeline(file)
        cc.export_edl(join(folder, (name + "-cut.edl")))
        cc._cleanup()
        queue.put({"percent": 100, "state": "done", "file": join(folder, (name + "-cut.edl"))})
    except Exception as e:
        queue.put({"percent": 100, "state": f"Error: {e}"})
        cc._cleanup()

col1, col2 = st.columns(2)
with col1:
    if st.button("Cut Single Clip (EDL)"):
        if os.path.isfile(input_path):
            result_file = run_task_with_progress(cut_clip_process, input_path)
            if result_file and os.path.exists(result_file):
                with open(result_file, "r") as f:
                    st.download_button(label="⬇️ Download EDL", data=f.read(), file_name=os.path.basename(result_file))
        else:
            st.error("Provided path is not a file.")
with col2:
    if st.button("Cut Folder (Merge to EDL)"):
        if os.path.isdir(input_path):
            result_file = run_task_with_progress(cut_folder_process, input_path)
            if result_file and os.path.exists(result_file):
                with open(result_file, "r") as f:
                    st.download_button(label="⬇️ Download Merged EDL", data=f.read(), file_name=os.path.basename(result_file))
        else:
            st.error("Provided path is not a directory.")

st.divider()

# ----------------- Audio Transcription -----------------
st.header("📝 Audio Transcriber (Whisper)")

def transcribeProcess(queue, filename):
    try:
        trans = Translator.translator(queue, selected_model)
        trans.audioToText(filename, preprocess=preprocess_audio, denoise=denoise_audio)
        out_name = os.path.splitext(filename)[0] + ".txt"
        queue.put({"percent": 100, "state": "done", "file": out_name})
    except Exception as e:
        queue.put({"percent": 100, "state": f"Error: {e}"})

def transcribeFolderProcess(queue, folder):
    try:
        files = []
        for ext in ("*.mkv", "*.mp4", "*.mov", "*.avi", "*.wav", "*.mp3", "*.MKV", "*.MP4", "*.MOV", "*.AVI", "*.WAV", "*.MP3"):
            files.extend(glob(join(folder, ext)))
        files.sort(key=getmtime)

        if not files:
            queue.put({"percent": 100, "state": "Error: No media files found"})
            return

        trans = Translator.translator(queue, selected_model)
        combined_parts = []
        for i, file in enumerate(files):
            queue.put({"percent": int((i/len(files))*100), "state": f"Transcribing {os.path.basename(file)}"})
            text = trans.transcribeFile(file, preprocess=preprocess_audio, denoise=denoise_audio)
            if combine_transcripts:
                if add_chapters:
                    combined_parts.append(f"\n## {os.path.basename(file)}\n\n{text}\n")
                else:
                    combined_parts.append(text)
            else:
                # write per-file transcript
                with open(os.path.splitext(file)[0] + ".txt", "w+") as f:
                    f.write(text)

        out_file = None
        if combine_transcripts:
            folder_name = os.path.basename(os.path.normpath(folder))
            out_file = os.path.join(folder, f"{folder_name}-transcript.txt")
            sep = "\n" if add_chapters else " "
            with open(out_file, "w+") as f:
                f.write(sep.join(combined_parts).strip())

        queue.put({"percent": 100, "state": "done", "file": out_file})
    except Exception as e:
        queue.put({"percent": 100, "state": f"Error: {e}"})

col_trans_1, col_trans_2 = st.columns(2)
with col_trans_1:
    if st.button("Transcribe Single File"):
        if os.path.isfile(input_path):
            result_file = run_task_with_progress(transcribeProcess, input_path)
            if result_file and os.path.exists(result_file):
                with open(result_file, "r") as f:
                    st.download_button(label="⬇️ Download Transcript", data=f.read(), file_name=os.path.basename(result_file))
        else:
            st.error("Provided path is not a file.")

with col_trans_2:
    if st.button("Transcribe Entire Folder"):
        if os.path.isdir(input_path):
            result_file = run_task_with_progress(transcribeFolderProcess, input_path)
            if result_file and os.path.exists(result_file):
                with open(result_file, "r") as f:
                    st.download_button(label="⬇️ Download Combined Transcript", data=f.read(), file_name=os.path.basename(result_file))
        else:
            st.error("Provided path is not a directory.")