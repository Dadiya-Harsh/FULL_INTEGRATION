import atexit
from flask import Flask, request, jsonify
from processor import process_new_meetings
from models import (
    EmployeeSkills,
    SkillRecommendation,
    TaskRecommendation,
    RollingSentiment,
    SessionLocal
)
from utils import get_sentiment_and_recommendations
import json
import re

app = Flask(__name__)


from apscheduler.schedulers.background import BackgroundScheduler
from processor import * 
def scheduled_processing():
    with app.app_context():
        process_new_meetings()

# Schedule to run every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_processing, trigger="interval", minutes=5)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


from transformers import pipeline
from sentiment import * 
# Load sentiment analysis model
sentiment_pipeline = pipeline("sentiment-analysis")

@app.route("/upload_transcript", methods=["POST"])
def upload_transcript():
    meeting_id = request.form.get("meeting_id")
    people_info = request.form.get("people_info")
    file = request.files["transcript"]

    if not all([meeting_id, people_info, file]):
        return jsonify({"error": "Missing input"}), 400

    try:
        people = json.loads(people_info)
    except Exception:
        return jsonify({"error": "Invalid JSON format for people_info"}), 400

    transcript = file.read().decode("utf-8")
    db = SessionLocal()
    responses = []

    for person in people:
        name = person["name"]
        role = person["role"]

        pattern = re.compile(rf"{name}\s*:\s*(.*)", re.IGNORECASE)
        person_lines = "\n".join([m.group(0) for m in pattern.finditer(transcript)])

        if not person_lines:
            responses.append({ "name": name, "error": "No dialogue found" })
            continue
        print(f"Person Line : {person} : {name} : {person_lines} ")
        print(f"Responses : {responses}")
        sentiment, skills, tasks = get_sentiment_and_recommendations(person_lines, name)

        rolling_data = get_rolling_sentiment_from_transcript(person_lines, name)
        # Sentiment_performance_score = rolling_data['Rolling Sentiment'].avg()
        rolling_sentiments = [entry['Rolling Sentiment'] for entry in rolling_data]  # Extract all the sentiment values
        print("Rolling sentiment : ",rolling_sentiments)
        # Then calculate the average
        average_sentiment = sum(rolling_sentiments) / len(rolling_sentiments) if rolling_sentiments else 0
        average_sentiment = round(average_sentiment,2)


        db.add(EmployeeSkills(
            meeting_id=meeting_id,
            overall_sentiment_score=average_sentiment,
            role=role,
            employee_name=name
        ))

        skill_responses = []
        if skills:
            for skill in skills[:3]:  # Ensure max 3 skills
                db.add(SkillRecommendation(
                    meeting_id=meeting_id,
                    skill_recommendation=skill,
                    name=name
                ))
                skill_responses.append(skill)


        task_responses = []
        if tasks:
            for task in tasks:
                db.add(TaskRecommendation(
                    meeting_id=meeting_id,
                    task=task["task"],
                    assigned_by=task["assigned_by"] or name,
                    assigned_to=task["assigned_to"] or name,
                    deadline=task["deadline"] or "N/A",
                    status=task["status"] or "Pending"
                ))
                task_responses.append({
                    "task": task["task"],
                    "assigned_by": task["assigned_by"],
                    "assigned_to": task["assigned_to"],
                    "deadline": task["deadline"],
                    "status": task["status"]
                })

        if rolling_data:
            db.add(RollingSentiment(
                meeting_id=meeting_id,
                name=name,
                role=role,
                rolling_sentiment=json.dumps(rolling_data)  # 🔥 Now in clean format
            ))

        responses.append({
            "name": name,
            "role": role,
            "sentiment_score": average_sentiment,
            "skill": skill_responses,
            "tasks": task_responses,
            "rolling_sentiment": rolling_data
        })

    db.commit()
    db.close()

    return jsonify({
        "message": "Processed all users successfully.",
        "data": responses
    })

@app.route("/")
def home():
    return "Server is up!"


@app.route("/process_unprocessed", methods=["POST"])
def process_unprocessed():
    try:
        result = process_new_meetings()
        if "error" in result:
            return jsonify({"status": "error", "message": result["error"]}), 500
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
if __name__ == "__main__":
    app.run(debug=True)
