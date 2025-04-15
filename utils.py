import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
import json
from groq import Groq
from models import *
from sentiment import *
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

genai.configure(api_key=os.getenv("GENAI_API_KEY"))
def get_sentiment_and_recommendations(text, person_name):
    prompt = f"""
        Analyze the transcript and focus ONLY on statements made by **{person_name}**.
        Analyze the following transcript and extract tasks along with the roles or names of the individuals involved:
                - Identify who assigned the task ("assigned_by").
                - Identify who is responsible for completing the task ("assigned_to").
                - Extract the task description and any deadlines (if mentioned).
        Examples of task assignments:
                - "Manager: John, please prepare the report by Friday."
                assigned_by: "Manager", assigned_to: "John", task: "Prepare the report", deadline: "Friday"
                - "Employee: I'll handle the client meeting next week."
                assigned_by: "Employee", assigned_to: "Employee", task: "Handle the client meeting", deadline: "Next week"

        Respond in the following strict JSON format ONLY:

{{
  "sentiment_score": float (0 to 1),
  "skills": [
    "Top skill recommendation 1",
    "Top skill recommendation 2",
    "Top skill recommendation 3"  // Maximum 3 skills
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

Rules:
1. Provide maximum 3 most important skills
2. Skills should be concise (3-5 words each)
3. Omit the skills array if no skills identified

Transcript:
{text}
    """

    # model = genai.GenerativeModel("gemini-1.5-pro-latest")
    try:
        # response = model.generate_content(prompt)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
            temperature=0.3  # More deterministic output
        )
        
        response_text = chat_completion.choices[0].message.content
        return parse_response(response_text)
    except Exception as e:
        print(f"Error generating content: {e}")
        return 0.0, [], []  # Return default values on error


def parse_response(response_text):
    try:
        json_match = re.search(r"\{[\s\S]+\}", response_text.strip())
        if not json_match:
            raise ValueError("No JSON found in response")

        json_data = json.loads(json_match.group())

        sentiment = float(json_data.get("sentiment_score", 0))
        print("SENTIMENT :=========,RESPONSE TEXT",sentiment,response_text)
        print("RESPONSE TEXT : ",response_text)
        skills = json_data.get("skills", [])[:3]  # Limit to max 3 skills
        
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
    

def get_rolling_sentiment_from_transcript(transcript: str, name: str):
    import nltk
    nltk.download("punkt", quiet=True)
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(transcript)
    result_data = []

    index = 1  # Sentence-wise index for the whole transcript
    for sentence in sentences:
        if sentence.lower().startswith(name.lower() + ":"):
            text = sentence.split(":", 1)[1].strip()  # Get text after "Name:"
            if text:
                # result = sentiment_pipeline(text)[0]
                # label = result["label"]
                # score = result["score"]

                # Convert to 0–100 sentiment score
                # sentiment_score = score * 100 if label == "POSITIVE" else (1 - score) * 100
                sentiment_score = get_sentiment(text)
                print("APP : ",sentiment_score)
                result_data.append({
                    "Index": index,
                    "Rolling Sentiment": round(sentiment_score, 2)
                })
        index += 1  # Increase index regardless of who said it

    return result_data


def process_meeting(meeting_id, db):
    try:
        # Get all unprocessed transcripts for this meeting
        transcripts = db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id,
            MeetingTranscript.processed == False
        ).all()
        
        if not transcripts:
            return []

        # Verify the meeting exists
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
            
            # Process sentiment and recommendations
            _, skills, tasks = get_sentiment_and_recommendations(full_text, name)
            
            # Calculate rolling sentiment
            rolling_data = get_rolling_sentiment_from_transcript(full_text, name)
            overall_sentiment = get_sentiment(full_text)
            
            # Save to EmployeeSkills
            db.add(EmployeeSkills(
                meeting_id=meeting_id,
                overall_sentiment_score=overall_sentiment,
                role=data["role"],
                employee_name=name
            ))

            # Save skill recommendations
            for skill in skills[:3]:
                db.add(SkillRecommendation(
                    meeting_id=meeting_id,
                    skill_recommendation=skill,
                    name=name
                ))

            # Save task recommendations
            for task in tasks:
                db.add(TaskRecommendation(
                    meeting_id=meeting_id,
                    task=task["task"],
                    assigned_by=task["assigned_by"] or name,
                    assigned_to=task["assigned_to"] or name,
                    deadline=task["deadline"] or "N/A",
                    status=task["status"] or "Pending"
                ))

            # Save rolling sentiment
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

            # Mark transcripts as processed
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