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
    Modular speech processing pipeline for audio transcription with speaker diarization.
    
    This pipeline handles the complete process of converting audio to text with speaker
    identification through the following steps:
    1. Converts audio to WAV format with appropriate parameters for processing.
    2. Runs speaker diarization using NeMo ClusteringDiarizer to identify different speakers.
    3. Merges consecutive segments from the same speaker to improve readability.
    4. Transcribes each segment using Groq's distil-whisper-large-v3-en model (with rate limiting).
    5. Returns a structured transcript with speaker labels and timestamps.
    
    Attributes:
        input_audio (Path): Path to the input audio file.
        model (str): Model size/type to use for transcription.
        audio_stem (str): Base filename without extension.
        wav_file (str): Path to the converted WAV file.
        rttm_file (str): Path to the generated RTTM file with speaker segments.
        diarized_transcript (list): Final processed transcript with speaker labels.
    """

    def __init__(self, input_audio: str, model: str = "medium"):
        """
        Initialize the speech processing pipeline.
        
        Args:
            input_audio (str): Path to the input audio file.
            model (str, optional): Model size/type for transcription. Defaults to "medium".
        """
        self.input_audio = Path(input_audio)
        self.model = model
        self.audio_stem = self.input_audio.stem
        self.wav_file = None
        self.rttm_file = None
        self.diarized_transcript = None

    def run_pipeline(self) -> List[Dict[str, str]]:
        """
        Execute the complete speech processing pipeline.
        
        Runs all steps of the pipeline in sequence: audio conversion, diarization,
        RTTM file processing, transcription, and cleanup.
        
        Returns:
            List[Dict[str, str]]: List of transcript segments with speaker labels,
                                 containing 'speaker', 'start', 'end', and 'text' keys.
        """
        self._convert_to_wav()
        self._run_diarization()
        self._locate_rttm()
        transcript = self._transcribe_segments()
        self._cleanup()
        return transcript

    def _convert_to_wav(self):
        """
        Convert the input audio to 16kHz mono WAV format and normalize waveform shape.

        If the input is not in WAV format, it is converted using ffmpeg.
        If the input is already a WAV file, it is reprocessed to ensure mono channel,
        16kHz sampling rate, and 1D waveform shape compatible with downstream models.

        The final waveform is saved to a consistent WAV file path, and
        self.wav_file is set accordingly.
        """

        def normalize_waveform(waveform: torch.Tensor) -> torch.Tensor:
            """
            Ensure waveform is mono and 1D.

            Converts a stereo waveform to mono by averaging channels,
            and flattens [1, T] shapes to [T].

            Args:
                waveform (torch.Tensor): Audio waveform loaded by torchaudio.

            Returns:
                torch.Tensor: A normalized mono waveform with shape [T].
            """
            if waveform.ndim == 2 and waveform.shape[0] == 1:
                return waveform.squeeze(0)
            elif waveform.ndim == 2 and waveform.shape[0] > 1:
                return waveform.mean(dim=0)
            return waveform

        self.wav_file = f"{self.audio_stem}.wav"

        # Always reprocess audio for consistency, even if already .wav
        logging.info("Normalizing and converting to WAV (16kHz mono)...")
        waveform, sr = torchaudio.load(str(self.input_audio))
        waveform = normalize_waveform(waveform)

        # Resample to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            waveform = resampler(waveform)
            sr = 16000

        # Save normalized audio
        torchaudio.save(self.wav_file, waveform.unsqueeze(0), sr)


    def _run_diarization(self):
        """
        Run NeMo Clustering Diarizer to generate speaker labels and RTTM file.

        Creates a manifest file for the audio, configures the diarizer,
        and executes the diarization process. The result is an RTTM file
        containing speaker segments.
        """
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
        """
        Find the generated RTTM file from the diarization process.
        
        Searches for the RTTM file matching the audio filename and sets
        self.rttm_file to its path.
        
        Raises:
            FileNotFoundError: If no matching RTTM file is found.
        """
        matches = glob.glob(f"**/{self.audio_stem}.rttm", recursive=True)
        if not matches:
            raise FileNotFoundError("RTTM not found.")
        self.rttm_file = matches[0]
        logging.info(f"Found RTTM: {self.rttm_file}")

    def _parse_rttm(self) -> List[Dict[str, float]]:
        """
        Extract segment information from the RTTM file.
        
        Parses the RTTM file to extract speaker segments with start times,
        durations, and speaker labels.
        
        Returns:
            List[Dict[str, float]]: List of segment dictionaries with 'speaker',
                                   'start', and 'end' keys.
        """
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
        Merge consecutive segments from the same speaker if they are close together.
        
        Combines segments from the same speaker if the gap between them is less
        than the specified threshold, improving transcript readability.
        
        Args:
            segments (List[Dict[str, float]]): List of segment dictionaries.
            gap_threshold (float, optional): Maximum gap in seconds between
                                           segments to merge. Defaults to 1.0.
        
        Returns:
            List[Dict[str, float]]: List of merged segment dictionaries.
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
        """
        Transcribe an audio segment using Groq's API with rate limiting.
        
        Makes a rate-limited call to Groq's API to transcribe the audio
        in the provided file.
        
        Args:
            filepath (str): Path to the audio file to transcribe.
            
        Returns:
            str: Transcribed text from the audio segment.
            
        Raises:
            ValueError: If GROQ_API_KEY is not set in environment variables.
            Exception: If there's an error with the Groq API call.
            
        Note:
            This method is rate-limited to 10 calls per 60 seconds.
        """
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set. Please set it before running the pipeline.")
        
        try:
            client = Groq(api_key=api_key)
            with open(filepath, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(filepath, file.read()),
                    model="distil-whisper-large-v3-en",
                    response_format="verbose_json",
                )
            return transcription.text.strip()
        except Exception as e:
            logging.error(f"Error transcribing audio with Groq API: {str(e)}")
            raise Exception(f"Failed to transcribe audio segment: {str(e)}")

    def _transcribe_segments(self) -> List[Dict[str, str]]:
        """
        Transcribe each merged segment from the RTTM file.
        
        Loads the audio file, extracts segments based on the RTTM file,
        merges close segments, and transcribes each segment using Groq's API.
        
        Returns:
            List[Dict[str, str]]: List of transcript segments with 'speaker',
                                 'start', 'end', and 'text' keys.
        """
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
        """
        Remove temporary files and folders created during processing.
        
        Deletes manifest files, WAV files, RTTM files, and temporary
        directories created during the diarization and transcription process.
        """
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
        """
        Download and return the path to the NeMo diarization configuration file.
        
        Checks if the configuration file exists locally, and if not,
        downloads it from the URL specified in the environment variables.
        
        Returns:
            str: Path to the diarization configuration file.
        """
        path = "diar_infer_telephonic.yaml"
        url = os.getenv("DIARIZATION_CONFIG_URL") 
        if not os.path.exists(path):
            logging.info("Downloading diarization config...")
            urllib.request.urlretrieve(url, path)
        return path
