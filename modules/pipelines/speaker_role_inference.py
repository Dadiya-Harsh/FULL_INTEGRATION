from modules.pipelines.speaker_diarization_based_transcription_pipeline import SpeechProcessingPipeline
from modules.db.postgres import insert_transcript
from modules.prompts import identify_speaker_role_prompt, format_transcript_for_roles
from modules.llm import get_groq_response
import json

class SpeakerRoleInferencePipeline:
    def __init__(self, audio_file_path: str):
        """
        Initialize the speaker role inference pipeline.

        Args:
            audio_file_path (str): Path to the audio file to process
        """
        self.audio_file_path = audio_file_path
        self.transcript = None
        self.speech_pipeline = None
        self.num_speakers = 0

    def run(self):
        """
        Runs the complete pipeline from audio to enriched transcript.

        Returns:
            list: Enriched transcript with speaker roles
        """
        transcript = self.diarize_and_transcribe(self.audio_file_path)
        samples = self.sample_utterances(transcript)
        role_mapping = self.identify_roles(samples)
        enriched_transcript = self.label_full_transcript(transcript, role_mapping)
        self.insert_to_db(enriched_transcript)
        return enriched_transcript

    def run_for_raw_transcript(self):
        """
        Returns sampled utterances for preview before mapping.

        Also determines the number of speakers in the audio.

        Returns:
            tuple: (samples, num_speakers) where samples is a list of utterances
                  and num_speakers is the count of unique speakers
        """
        self.speech_pipeline = SpeechProcessingPipeline(self.audio_file_path)
        self.transcript = self.speech_pipeline.run_pipeline()
        self.num_speakers = self.speech_pipeline.get_speaker_count()
        self.samples = self.sample_utterances(self.transcript)
        return self.samples, self.num_speakers

    def get_speaker_count(self):
        """
        Returns the number of unique speakers detected in the transcript.

        Returns:
            int: Number of unique speakers
        """
        return self.num_speakers

    def apply_manual_labels(self, speaker_labels: dict):
        """
        Maps manually provided speaker labels to the full transcript.
        """
        if self.transcript is None:
            self.transcript = self.diarize_and_transcribe(self.audio_file_path)

        labeled = []
        for entry in self.transcript:
            speaker_key = entry["speaker"].lower()  # Normalize to match keys like 'speaker_0'
            label = speaker_labels.get(speaker_key, speaker_key)
            labeled.append({**entry, "speaker": label})
        return labeled

    def diarize_and_transcribe(self, audio_path):
        """
        Processes audio file through speaker diarization and transcription.

        Uses SpeechProcessingPipeline to identify different speakers and
        transcribe their speech into text.

        Args:
            audio_path (str): Path to the audio file to process

        Returns:
            list: List of dictionaries containing speaker-labeled transcript segments
                  with keys 'speaker', 'start', 'end', and 'text'
        """
        return SpeechProcessingPipeline(audio_path).run_pipeline()

    def sample_utterances(self, transcript, max_per_speaker=3):
        """
        Creates a representative sample of utterances from each speaker in the transcript.

        This method intelligently selects utterances to provide a good preview of each speaker's
        contributions, focusing on meaningful content that helps with speaker identification.

        Args:
            transcript (list): List of transcript entries with speaker and text
            max_per_speaker (int, optional): Maximum utterances to sample per speaker. Defaults to 3.

        Returns:
            list: List of dictionaries with 'speaker' and 'text' keys
        """
        if not transcript or max_per_speaker <= 0:
            return []

        # Group utterances by speaker
        speaker_utterances = {}
        for entry in transcript:
            speaker = entry["speaker"]
            if speaker not in speaker_utterances:
                speaker_utterances[speaker] = []
            speaker_utterances[speaker].append(entry)

        samples = []

        # Process each speaker's utterances
        for speaker, utterances in speaker_utterances.items():
            # If we have fewer utterances than max_per_speaker, use all of them
            if len(utterances) <= max_per_speaker:
                selected = utterances
            else:
                # Create a balanced and representative sample
                selected = self._create_representative_sample(utterances, max_per_speaker)

            # Add the selected utterances to our samples
            for entry in selected:
                samples.append({
                    "speaker": speaker,
                    "text": entry["text"]
                })

        return samples

    def _create_representative_sample(self, utterances, max_samples):
        """
        Creates a representative sample from a list of utterances.

        This helper method combines multiple sampling techniques to create the most
        informative sample possible:
        1. Includes utterances from different parts of the conversation
        2. Prioritizes longer, more content-rich utterances
        3. Avoids very short or uninformative utterances

        Args:
            utterances (list): List of utterances from a single speaker
            max_samples (int): Maximum number of samples to select

        Returns:
            list: Selected utterances that form a representative sample
        """
        # Filter out very short utterances (less than 5 characters)
        filtered = [u for u in utterances if len(u["text"]) >= 5]
        if not filtered:
            filtered = utterances  # Fall back to all utterances if all are short

        # If we still have more utterances than needed, create a balanced sample
        if len(filtered) <= max_samples:
            return filtered

        # Calculate a content score for each utterance (length is a simple proxy for content)
        for u in filtered:
            u["_content_score"] = len(u["text"])

        # Sort by content score (descending)
        sorted_by_content = sorted(filtered, key=lambda x: x["_content_score"], reverse=True)

        # Always include the highest-scoring utterance
        selected = [sorted_by_content[0]]

        # For the remaining slots, select utterances from different parts of the conversation
        remaining = max_samples - 1
        if remaining > 0:
            # Get utterances from the original chronological order
            # but exclude the one we've already selected
            highest_score_text = selected[0]["text"]
            chronological = [u for u in utterances if u["text"] != highest_score_text]

            # Select from beginning, end, and middle as needed
            indices = []
            if remaining >= 2:
                indices.extend([0, len(chronological) - 1])  # Beginning and end
                remaining -= 2
            elif remaining == 1:
                indices.append(0)  # Just the beginning
                remaining -= 1

            # Add middle points as needed
            if remaining > 0 and len(chronological) > 2:
                step = len(chronological) / (remaining + 1)
                for i in range(1, remaining + 1):
                    idx = min(int(i * step), len(chronological) - 1)
                    indices.append(idx)

            # Sort indices to maintain chronological order
            indices.sort()

            # Add the selected utterances
            for idx in indices:
                if idx < len(chronological):
                    selected.append(chronological[idx])

        # Remove the temporary content score
        for u in selected:
            if "_content_score" in u:
                del u["_content_score"]

        return selected

    def identify_roles(self, samples):
        """
        Identifies speaker roles based on sampled utterances.

        Uses LLM to analyze speech patterns and content to infer
        the most likely role for each speaker.

        Args:
            samples (list): List of dictionaries with speaker utterances

        Returns:
            dict: Mapping of speaker IDs to inferred roles

        Raises:
            json.JSONDecodeError: If LLM response cannot be parsed as JSON
        """
        formatted = format_transcript_for_roles(samples)
        prompt = identify_speaker_role_prompt(formatted)

        # logger.info("Calling Groq LLM to classify speaker roles...")
        raw_response = get_groq_response(prompt)

        try:
            role_mapping = json.loads(raw_response)
            return role_mapping
        except json.JSONDecodeError:
            # logger.error("LLM returned malformed JSON. Response:\n" + raw_response)
            raise

    def label_full_transcript(self, transcript, role_mapping):
        """
        Applies role labels to the full transcript.

        Maps the identified roles from the role_mapping dictionary
        to each entry in the complete transcript.

        Args:
            transcript (list): Complete transcript with speaker IDs
            role_mapping (dict): Mapping of speaker IDs to role labels

        Returns:
            list: Transcript with speaker IDs replaced by role labels
        """
        return [
            {**entry, "speaker": role_mapping.get(f"Speaker_{entry['speaker'].split('_')[1]}", entry['speaker'])}
            for entry in transcript
        ]

    def insert_to_db(self, enriched_transcript):
        """
        Persists the enriched transcript to the database.

        Stores the transcript with speaker role labels in the database
        for future reference and analysis.

        Args:
            enriched_transcript (list): Transcript with speaker roles applied

        Returns:
            None
        """
        insert_transcript(enriched_transcript)
