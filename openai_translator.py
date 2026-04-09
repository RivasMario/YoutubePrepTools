import subprocess
import tempfile
import os
from faster_whisper import WhisperModel
from os.path import splitext


class translator:
    def __init__(self, transcribe_queue, model):
        self.status_queue = transcribe_queue
        self.status_queue.put({"percent": 0.0, "state": "Loading Model"})
        self.model = WhisperModel(model, device="cpu", compute_type="int8")
        self.status_queue.put({"percent": 25, "state": "Model Ready"})

    def _preprocess_audio(self, fileName, denoise=False):
        """Extract + clean audio with ffmpeg. Returns path to temp wav."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        # highpass kills rumble; loudnorm normalizes volume; afftdn denoises (optional)
        filters = ["highpass=f=80", "loudnorm=I=-16:TP=-1.5:LRA=11"]
        if denoise:
            filters.insert(1, "afftdn=nf=-25")
        cmd = [
            "ffmpeg", "-y", "-i", fileName,
            "-vn", "-ac", "1", "-ar", "16000",
            "-af", ",".join(filters),
            tmp.name,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return tmp.name

    def transcribeFile(self, fileName, preprocess=False, denoise=False):
        """Transcribe a single file and return the text (no file write)."""
        target = fileName
        temp_audio = None
        if preprocess:
            try:
                temp_audio = self._preprocess_audio(fileName, denoise=denoise)
                target = temp_audio
            except Exception as e:
                print(f"Preprocessing failed, using original: {e}")
        try:
            segments, info = self.model.transcribe(
                target,
                beam_size=5,
                condition_on_previous_text=False,
                vad_filter=True,
            )
            return " ".join(segment.text.strip() for segment in segments)
        finally:
            if temp_audio and os.path.exists(temp_audio):
                os.unlink(temp_audio)

    def audioToText(self, fileName, preprocess=False, denoise=False):
        print("starting transcription")
        self.status_queue.put({"percent": 20, "state": "Preparing audio..."})
        self.status_queue.put({"percent": 33, "state": "Transcribing..."})
        text = self.transcribeFile(fileName, preprocess=preprocess, denoise=denoise)
        name, extension = splitext(fileName)
        self.status_queue.put({"percent": 95, "state": "Transcription Complete"})
        with open(name + ".txt", "w+") as text_file:
            text_file.write(text)
        self.status_queue.put({"percent": 100, "state": "done"})
