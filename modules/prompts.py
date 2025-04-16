from typing import List, Dict

def identify_speaker_role_prompt(formatted_transcript: str) -> str:
    return f"""
    You are a precise and analytical meeting role classifier. Your task is to determine the most likely real-world role for each speaker based solely on their dialogue in the provided transcript.

    Consider roles such as "Product Manager", "Client Lead", "Sales Executive", "Technical Engineer", "CTO", or other relevant professional roles.
    Analyze the language, tone, context, and content of each speaker’s dialogue to infer their role.
    Assign exactly one role per speaker. If multiple roles seem plausible, select the single most fitting role based on the dialogue’s primary focus and responsibilities implied.
    Avoid ambiguous or composite role names (e.g., do not use "Manager/Lead" or "Engineer/Developer").
    If the transcript lacks sufficient context for a definitive role, choose a role that best aligns with the speaker’s apparent expertise or function, prioritizing specificity over generic roles like "Manager".
    IMPORTANT: Return ONLY the JSON mapping in the exact format below. Do not include any additional text, explanations, or commentary.

    Expected JSON format:

    json

    Copy
    {
    "Speaker_0": "<role>",
    "Speaker_1": "<role>"
    }
    Transcript:
    {formatted_transcript}
    """.strip()

def format_transcript_for_roles(transcript: List[Dict[str, str]]) -> str:
    return "\n".join([f"{seg['speaker']}: {seg['text']}" for seg in transcript])
