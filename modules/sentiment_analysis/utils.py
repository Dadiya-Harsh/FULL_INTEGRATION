#=====================================
#Imports and Environment Setup
#=====================================
import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
import nltk

from modules.db.models import *
from modules.sentiment_analysis.sentiment import *

load_dotenv()

# Configure external APIs
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GENAI_API_KEY"))

#===============================
# CHUNKING FUNCTION
#===============================

# def chunk_text(text, max_tokens=2048, overlap=200):
#     sentences = nltk.sent_tokenize(text)
#     chunks = []
#     current_chunk = []
#     current_len = 0

#     for sentence in sentences:
#         sentence_len = len(sentence.split())

#         if current_len + sentence_len > max_tokens:
#             chunks.append(" ".join(current_chunk))
#             current_chunk = current_chunk[-overlap:]  # maintain context
#             current_len = sum(len(s.split()) for s in current_chunk)

#         current_chunk.append(sentence)
#         current_len += sentence_len

#     if current_chunk:
#         chunks.append(" ".join(current_chunk))

#     return chunks

#=====================================
# Main Sentiment & Recommendation Extractor
#=====================================

def get_sentiment_and_recommendations(text, person_name):
    prompt = f"""
        Analyze the transcript and focus ONLY on statements made by **{person_name}**.
        Extract tasks with:
        - assigned_by
        - assigned_to
        - task
        - deadline
        - status

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
        return 0.0, [], []


# def get_sentiment_and_recommendations(text, person_name):
#     chunks = chunk_text(text)

#     all_skills = set()
#     all_tasks = []
#     sentiment_scores = []

#     for chunk in chunks:
#         prompt = f"""
#         Analyze ONLY {person_name}'s speech.
#         Extract sentiment score, top 3 skills, and any tasks using this JSON format:
#         {{
#           "sentiment_score": float (0 to 1),
#           "skills": ["skill1", "skill2", "skill3"],
#           "tasks": [{{"task": "...", "assigned_by": "...", "assigned_to": "...", "deadline": "...", "status": "..."}}]
#         }}

#         Transcript:
#         {chunk}
#         """

#         try:
#             chat_completion = client.chat.completions.create(
#                 messages=[{"role": "user", "content": prompt}],
#                 model="llama3-8b-8192",
#                 response_format={"type": "json_object"},
#                 temperature=0.3
#             )
#             response_text = chat_completion.choices[0].message.content
#             data = parse_response(response_text)

#             sentiment_scores.append(data["sentiment_score"])
#             all_skills.update(data["skills"])
#             all_tasks.extend(data["tasks"])

#         except Exception as e:
#             print(f"Chunk error: {e}")

#     avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5
#     top_skills = list(all_skills)[:3] if all_skills else []

#     return avg_sentiment, top_skills, all_tasks



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

        results = []
        for name, data in participants.items():
            full_text = "\n".join(data["texts"])

            _, skills, tasks = get_sentiment_and_recommendations(full_text, name)
            rolling_data = get_rolling_sentiment_from_transcript(full_text, name)

            speaker_text = " ".join([
                sentence.split(":", 1)[1].strip()
                for sentence in full_text.split("\n")
                if sentence.lower().startswith(name.lower() + ":")
            ])
            print("=====================SPEAKER TEXT=====================")
            print(f'Spaekar Name :- {name},Speaker Text:{speaker_text}')
            print("=====================================================")
            
            if speaker_text:
                overall_sentiment= get_sentiment(speaker_text)
                print("=====================================================")
                print("OVERALL SENTIMENT : ",overall_sentiment)
                print("=====================================================")
            else:
                overall_sentiment = 50.0
            
            # advanced_scores = get_detailed_scores_from_llm(speaker_text, name)
            # Save to DB
            db.add(EmployeeSkills(
                meeting_id=meeting_id,
                overall_sentiment_score=overall_sentiment,
                role=data["role"],
                employee_name=name
            ))

            for skill in skills[:3]:
                db.add(SkillRecommendation(
                    meeting_id=meeting_id,
                    skill_recommendation=skill,
                    name=name
                ))

            for task in tasks:
                (TaskRecommendation(
                    meeting_id=meeting_id,
                    task=task["task"],
                    assigned_by=task["assigned_by"] or name,
                    assigned_to=task["assigned_to"] or name,
                    deadline=task["deadline"] or "N/A",
                    status=task["status"] or "Pending"
                ))

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

            # Mark transcript as processed
            for transcript in transcripts:
                if transcript.name == name:
                    transcript.processed = True

            results.append({
                "meeting_id": meeting_id,
                "name": name,
                "role": data["role"],
                "sentiment": overall_sentiment,
                "skills": skills,
                "tasks": tasks,
                "rolling_sentiment": rolling_data
            })

        return results

    except Exception as e:
        db.rollback()
        raise e
