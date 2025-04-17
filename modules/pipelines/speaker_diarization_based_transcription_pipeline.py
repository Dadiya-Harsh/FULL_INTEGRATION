import os
import glob
import json
import torch
import shutil
import logging
import subprocess
import tempfile
import torchaudio
import urllib.request
from tqdm import tqdm
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict
from omegaconf import OmegaConf
from nemo.collections.asr.models import ClusteringDiarizer
from ratelimit import limits, sleep_and_retry
from groq import Groq

load_dotenv()

# Configure logging
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
device = 0 if torch.cuda.is_available() else -1

class SpeechProcessingPipeline:
    """
    Modular speech processing pipeline:
    1. Converts audio to WAV.
    2. Runs speaker diarization (NeMo ClusteringDiarizer).
    3. Merges consecutive segments for the same speaker.
    4. Transcribes each segment using Groq's distil-whisper-large-v3-en (rate-limited).
    5. Returns speaker-labeled transcript.
    """

    def __init__(self, input_audio: str, num_speakers: int = 2, model: str = "medium"):
        self.input_audio = Path(input_audio)
        self.num_speakers = num_speakers
        self.model = model
        self.audio_stem = self.input_audio.stem
        self.wav_file = None
        self.rttm_file = None
        self.diarized_transcript = None

    def run_pipeline(self) -> List[Dict[str, str]]:
        self._convert_to_wav()
        self._run_diarization()
        self._locate_rttm()
        transcript = self._transcribe_segments()
        self._cleanup()
        return transcript

    def _convert_to_wav(self):
        """Converts the input audio to 16kHz mono WAV if needed."""
        if self.input_audio.suffix == ".wav":
            self.wav_file = str(self.input_audio)
            logging.info("Input is already in WAV format.")
            return

        self.wav_file = f"{self.audio_stem}.wav"
        logging.info("Converting to WAV...")
        command = f"ffmpeg -i {self.input_audio} -ar 16000 -ac 1 {self.wav_file} -y"
        subprocess.run(command, shell=True, check=True)

    def _run_diarization(self):
        """Runs NeMo Clustering Diarizer to generate speaker labels and RTTM."""
        config_path = self._ensure_diarization_config()
        manifest = {
            "audio_filepath": self.wav_file,
            "offset": 0,
            "duration": None,
            "label": "infer",
            "text": "-",
            "num_speakers": None,
            "rttm_filepath": None,
            "uem_filepath": None
        }

        # Write the manifest to file.
        with open("manifest.json", "w") as f:
            json.dump(manifest, f)
            f.write("\n")

        config = OmegaConf.load(config_path)
        config.diarizer.manifest_filepath = "manifest.json"
        config.diarizer.out_dir = "./"
        config.diarizer.speaker_embeddings.model_path = "titanet_large"
        config.diarizer.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        config.diarizer.clustering.parameters.oracle_num_speakers = False

        logging.info("Running diarization...")
        diarizer = ClusteringDiarizer(cfg=config)
        if not torch.cuda.is_available():
            logging.warning("CUDA not available. Diarization will run on CPU and might be slow.")
        diarizer.diarize()

    def _locate_rttm(self):
        """Finds the generated RTTM file."""
        matches = glob.glob(f"**/{self.audio_stem}.rttm", recursive=True)
        if not matches:
            raise FileNotFoundError("RTTM not found.")
        self.rttm_file = matches[0]
        logging.info(f"Found RTTM: {self.rttm_file}")

    def _parse_rttm(self) -> List[Dict[str, float]]:
        """Extracts segment information from the RTTM file."""
        segments = []
        with open(self.rttm_file) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 8 or parts[0] != "SPEAKER":
                    continue
                start = float(parts[3])
                duration = float(parts[4])
                segments.append({
                    "speaker": parts[7],
                    "start": start,
                    "end": start + duration
                })
        return segments

    def merge_segments(self, segments: List[Dict[str, float]], gap_threshold: float = 1.0) -> List[Dict[str, float]]:
        """
        Merge consecutive segments for the same speaker if the gap between them is less than gap_threshold (seconds).
        """
        if not segments:
            return []
        merged = [segments[0]]
        for seg in segments[1:]:
            last = merged[-1]
            if seg["speaker"] == last["speaker"] and seg["start"] - last["end"] <= gap_threshold:
                last["end"] = seg["end"]
            else:
                merged.append(seg)
        return merged

    @sleep_and_retry
    @limits(calls=10, period=60)  
    def _groq_transcribe(self, filepath: str) -> str:
        """Makes a rate-limited call to Groq to transcribe the audio segment in the provided file."""
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        with open(filepath, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filepath, file.read()),
                model="distil-whisper-large-v3-en",
                response_format="verbose_json",
            )
        return transcription.text.strip()

    def _transcribe_segments(self) -> List[Dict[str, str]]:
        """Transcribes each merged segment from RTTM and returns the results."""
        waveform, sr = torchaudio.load(self.wav_file)
        segments = self._parse_rttm()
        segments = self.merge_segments(segments, gap_threshold=1.0)  # Merge segments that are close
        results = []
        logging.info("Transcribing segments...")

        for seg in tqdm(segments, desc="Transcribing", unit="segment"):
            start_sample = max(0, int(seg["start"] * sr))
            end_sample = min(waveform.shape[1], int(seg["end"] * sr))
            audio_chunk = waveform[:, start_sample:end_sample]

            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                torchaudio.save(tmp.name, audio_chunk, sr)
                transcription_text = self._groq_transcribe(tmp.name)
            results.append({
                "speaker": seg["speaker"],
                "start": seg["start"],
                "end": seg["end"],
                "text": transcription_text
            })

        self.diarized_transcript = results
        return results

    def _cleanup(self):
        """Removes temporary files and folders created during processing."""
        files_to_delete = [
            "manifest.json",
            "manifest_vad_input.json",
            self.wav_file,
            self.rttm_file
        ]
        folders_to_delete = [
            "vad_outputs",
            "speaker_outputs",
            "pred_rttms"
        ]
        for file in files_to_delete:
            if file and os.path.exists(file):
                os.remove(file)
        for folder in folders_to_delete:
            if os.path.exists(folder):
                shutil.rmtree(folder)
        logging.info("Temporary files and folders cleaned up.")

    @staticmethod
    def _ensure_diarization_config() -> str:
        """Downloads and returns the path to the NeMo diarization configuration file if missing."""
        path = "diar_infer_telephonic.yaml"
        url = os.getenv("DIARIZATION_CONFIG_URL") 
        if not os.path.exists(path):
            logging.info("Downloading diarization config...")
            urllib.request.urlretrieve(url, path)
        return path