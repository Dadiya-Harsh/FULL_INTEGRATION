#=====================================
#Imports and Environment Setup
#=====================================
import logging
import os
import re
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
import psycopg2

from modules.db.models import *
from modules.sentiment_analysis.sentiment import *
from nltk.tokenize import sent_tokenize
load_dotenv()
import time

# Configure external APIs
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


genai.configure(api_key=os.getenv("GENAI_API_KEY"))

#===============================
# CHUNKING FUNCTION
#===============================
from transformers import BartForConditionalGeneration, BartTokenizer
import nltk


# Load the BART model and tokenizer for summarization
model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')
tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')


# Function to count tokens in a string
def count_tokens(text):
    return len(tokenizer.encode(text))

# Function for summarizing text with BART
def summarize_text(text, max_input_length=1024, max_output_length=150):
    inputs = tokenizer.encode("summarize: " + text, return_tensors="pt", max_length=max_input_length, truncation=True)
    summary_ids = model.generate(inputs, max_length=max_output_length, num_beams=4, early_stopping=True)
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

# Function to chunk text to respect token limit (for the summarization process)
def chunk_text(text, max_tokens=1024, overlap=200):
    import nltk
    nltk.download("punkt", quiet=True)
    from nltk.tokenize import sent_tokenize
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence.split())  # Count words

        # Check if adding the sentence would exceed the token limit
        if current_len + sentence_len > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = current_chunk[-overlap:]  # Maintain overlap
            current_len = sum(len(s.split()) for s in current_chunk)

        current_chunk.append(sentence)
        current_len += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

# Function to chunk and summarize text (to handle long transcripts)
def chunk_and_summarize_text(text, max_input_length=1024, max_output_length=150, max_tokens=1024, overlap=200):
    # Here we chunk the text into manageable chunks of size `max_input_length`
    chunks = chunk_text(text, max_tokens=max_tokens, overlap=overlap)  # Pass the overlap parameter to chunk_text
    summaries = [summarize_text(chunk, max_input_length=max_input_length, max_output_length=max_output_length) for chunk in chunks]
    return " ".join(summaries)



#=====================================
# Main Sentiment & Recommendation Extractor
#=====================================
def get_tasks_from_llm(text):
    prompt = f"""
        Analyze the transcript and extract **only the top 3 most necessary tasks** mentioned in the conversation.
        A task is any responsibility, goal, or action item that is explicitly or implicitly assigned to someone.
        If a person **suggests, hints, or indirectly implies** a responsibility, goal, or action item,
        treat it as a task. Include reflective, planning, and preparatory tasks.

        Focus on identifying tasks that are most critical for outcomes, follow-ups, or decision-making.

        Respond in the following strict JSON format ONLY:
        {{
            "tasks": [
                {{
                    "task": "description",
                    "assigned_by": "Person assigning the task",
                    "assigned_to": "Person responsible for the task",
                    "deadline": "Suggested deadline",
                    "status": "Task status"
                }}
            ]
        }}

        Transcript:
        {text}
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
            temperature=0.3
        )

        response_text = chat_completion.choices[0].message.content
        _, _, tasks = parse_response(response_text)
        return tasks
        # return parse_response(response_text)
    except Exception as e:
        print(f"Error generating content: {e}")
        return []

 
def get_sentiment_and_recommendations(text, person_name):

    prompt = f"""
        Analyze the transcript and focus primarily on statements made by **{person_name}**,
        but interpret task context based on the full conversation if needed.

        Extract:
        - Sentiment score (0 to 1)
        - Up to 3 top skills inferred from the person's dialogues
        - All tasks they are expected to do (explicitly or implicitly assigned)

        If a person **suggests, hints, or indirectly implies** a responsibility, goal, or action item,
        treat it as a task. Include reflective, planning, and preparatory tasks.

        Respond in the following strict JSON format ONLY:
        {{
        "sentiment_score": float (0 to 1),
        "skills": [
            "Top skill 1",
            "Top skill 2",
            "Top skill 3"
        ],
        "tasks": [
            {{
            "task": "description",
            "assigned_by": "Person assigning the task",
            "assigned_to": "Person responsible for the task",
            "deadline": "Suggested deadline",
            "status": "Task status"
            }}
        ]
        }}

        Transcript:
        {text}
        """


    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
            temperature=0.3
        )

        response_text = chat_completion.choices[0].message.content
        return parse_response(response_text)
    except Exception as e:
        print(f"Error generating content: {e}")
        return []


#=====================================
# JSON Parser for AI Response
#=====================================


def parse_response(response_text):
    try:
        json_match = re.search(r"\{[\s\S]+\}", response_text.strip())
        if not json_match:
            raise ValueError("No JSON found in response")

        json_data = json.loads(json_match.group())
        sentiment = float(json_data.get("sentiment_score", 0))
        skills = json_data.get("skills", [])[:3]

        tasks = []
        for task_data in json_data.get("tasks", []):
            task = {
                "task": task_data.get("task", ""),
                "assigned_by": task_data.get("assigned_by", ""),
                "assigned_to": task_data.get("assigned_to", ""),
                "deadline": task_data.get("deadline", ""),
                "status": task_data.get("status", "")
            }
            tasks.append(task)

        return sentiment, skills, tasks

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return 0.0, [], []
    except Exception as e:
        print(f"General error parsing model output: {e}")
        return 0.0, [], []

#=====================================
#  Rolling Sentiment Processor (NLTK)
#=====================================

def get_rolling_sentiment_from_transcript(transcript: str, name: str):
    import nltk
    nltk.download("punkt", quiet=True)
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(transcript)
    result_data = []
    index = 1

    for sentence in sentences:
        if sentence.lower().startswith(name.lower() + ":"):
            text = sentence.split(":", 1)[1].strip()
            if text:
                sentiment_score = get_sentiment(text)
                result_data.append({
                    "Index": index,
                    "Rolling Sentiment": round(sentiment_score, 2)
                })
        index += 1

    return result_data

#=====================================
# Combined Sentiment using Transformer Model
#=====================================

from transformers import pipeline

# # Load model globally
sentiment_pipeline = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

def get_combined_sentiment(text: str):
    result = sentiment_pipeline(text[:512])[0]
    # result = sentiment_pipeline(text, truncation=True)[0]
    label = result['label']
    score = result['score']
    sentiment_score = score * 100 if "POSITIVE" in label else (1 - score) * 100
    return round(sentiment_score, 2), label




#=====================================
#  Meeting Processing Function
#=====================================



def process_meeting(meeting_id, db):
    try:
        transcripts = db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id,
            MeetingTranscript.processed == False
        ).all()

        if not transcripts:
            return []

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise ValueError(f"Meeting with ID {meeting_id} does not exist")

        participants = {}
        for transcript in transcripts:
            if transcript.name not in participants:
                employee = db.query(Employee).filter(Employee.name == transcript.name).first()
                participants[transcript.name] = {
                    "role": employee.role if employee else "Participant",
                    "texts": []
                }
            participants[transcript.name]["texts"].append(f"{transcript.name}: {transcript.text}")

        # ✅ Build the full meeting transcript
        full_meeting_transcript = "\n".join(
            f"{t.name}: {t.text}" for t in transcripts
        )

        # ✅ Get all tasks from the full meeting transcript
        all_tasks = get_tasks_from_llm(full_meeting_transcript)

        print("=====================================================")
        print('FULL MEETING TRANSCRIPT : ',full_meeting_transcript)
        print("===========================================")
        # ✅ Save extracted tasks to DB
        for task in all_tasks:
            db.add(TaskRecommendation(
                meeting_id=meeting_id,
                task=task["task"],
                assigned_by=task["assigned_by"],
                assigned_to=task["assigned_to"],
                deadline=task["deadline"] or "N/A",
                status=task["status"] or "Pending"
            ))

        print("=====================================================")
        print('ALL TASKS : ',all_tasks)
        print("=====================================================")

        results = []

        # Process each participant individually for skills, sentiments
        for name, data in participants.items():
            full_text = "\n".join(data["texts"])

            # Get sentiment & skills for individual
            _, skills, _ = get_sentiment_and_recommendations(full_text, name)

            rolling_data = get_rolling_sentiment_from_transcript(full_text, name)

            speaker_text = " ".join([
                sentence.split(":", 1)[1].strip()
                for sentence in full_text.split("\n")
                if sentence.lower().startswith(name.lower() + ":")
            ])

            print("=====================SPEAKER TEXT=====================")
            print(f'Speaker Name: {name}, Speaker Text: {speaker_text}')
            print("=====================================================")

            if speaker_text:
                overall_sentiment = get_sentiment(speaker_text)
                print("=====================================================")
                print("OVERALL SENTIMENT : ", overall_sentiment)
                print("=====================================================")
            else:
                overall_sentiment = 50.0

            # ✅ Save individual sentiment
            db.add(EmployeeSkills(
                meeting_id=meeting_id,
                overall_sentiment_score=overall_sentiment,
                role=data["role"],
                employee_name=name
            ))

            # ✅ Save skill recommendations
            for skill in skills[:3]:
                db.add(SkillRecommendation(
                    meeting_id=meeting_id,
                    skill_recommendation=skill,
                    name=name
                ))

            # ✅ Save rolling sentiment
            if rolling_data:
                db.add(RollingSentiment(
                    meeting_id=meeting_id,
                    name=name,
                    role=data["role"],
                    rolling_sentiment=json.dumps({
                        "scores": rolling_data,
                        "average": overall_sentiment
                    })
                ))

            # ✅ Mark transcripts processed
            for transcript in transcripts:
                if transcript.name == name:
                    transcript.processed = True

            # ✅ Return result data
            results.append({
                "meeting_id": meeting_id,
                "name": name,
                "role": data["role"],
                "sentiment": overall_sentiment,
                "skills": skills,
                "tasks": all_tasks,
                "rolling_sentiment": rolling_data
            })

        return results

    except Exception as e:
        db.rollback()
        raise e



#==========================================
# FETCH ALL EMPLOYEE FOR SPEAKER LABELLING
#==========================================


def fetch_all_employees():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables.")

    # Parse the URL into connection components
    result = urlparse(database_url)

    conn = psycopg2.connect(
        dbname=result.path[1:],  # remove leading slash
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    cur = conn.cursor()
    cur.execute("SELECT name FROM employee;")
    employee_names = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return employee_names



#========================================
# VALIDATE SPEAKER ROLES WITH LLM 
#=========================================
# from groq import Groq  # make sure this is installed: pip install groq

def validate_speaker_roles_with_llm(transcript):
    prompt = f"""
You are an AI assistant helping to review meeting transcripts.
Each part of the transcript is labeled with speakers like 'Speaker 0', 'Speaker 1', etc.

Please check the speakers' dialogues and suggest appropriate names for them based on the context of the conversation.

Return a JSON object in this format ONLY:
{{
  "status": "ok" or "correction_needed",
  "suggested_labels": {{
    "speaker_0": "Suggested Name 1",
    "speaker_1": "Suggested Name 2",
    ...
  }}
}}

Transcript:
{transcript}
"""

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192",
        response_format={"type": "json_object"},
        temperature=0.3
    )

    return chat_completion.choices[0].message.content

