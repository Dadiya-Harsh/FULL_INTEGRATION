import os
import sys
import requests
from threading import Thread
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

# 🛠️ Path Setup
sys.path.append(os.path.abspath("/home/dhruvin/AI_meeting_task/sentiment_analyzer_multi_speaker/Video_process/AI_meeting_task"))

# ✅ Core App Imports
from modules.db.models import DATABASE_URL
from modules.sentiment_analysis.processor import process_new_meetings
from Dashboard import employee_dashboard, hr_dashboard, login_page, manager_dashboard
from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline

# ===========================
# 🔁 BACKEND: Flask + Scheduler
# ===========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Flask backend is running!"

@app.route("/process_unprocessed", methods=["POST"])
def process_unprocessed():
    try:
        result = process_new_meetings()
        if "error" in result:
            return jsonify({"status": "error", "message": result["error"]}), 500
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def start_flask():
    app.run(port=5000, debug=False, use_reloader=False)

def scheduled_processing():
    print("⏰ Auto-scheduler triggered.")
    try:
        process_new_meetings()
    except Exception as e:
        print(f"Scheduled processing error: {e}")

# 🔄 Schedule background job
scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_processing, trigger="interval", minutes=1)
scheduler.start()

# ===========================
# 💬 CHATBOT TAB
# ===========================
import streamlit as st
from chatbot.app.chatbot_handler import ChatbotHandler
from chatbot.app.auth import authenticate_user
from chatbot.config.settings import DATABASE_URL, LLMConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sql_agent_tool import SQLAgentTool
from sql_agent_tool.models import DatabaseConfig

def chatbot_tab():
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

    db_config = DatabaseConfig(
        drivername=os.getenv("DB_DRIVER"),
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME")
    )
    sql_agent = SQLAgentTool(db_config, LLMConfig)

    if "chatbot_handler" not in st.session_state:
        st.session_state.chatbot_handler = ChatbotHandler(SessionLocal(), sql_agent)
        st.session_state.chat_history = []
        st.session_state.query = ""

    st.subheader(f"🤖 Welcome, User {st.session_state.user_name} - Chatbot")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"] if isinstance(msg["content"], str) else msg["content"].get("message", ""))

    st.session_state.query = st.text_input("Ask something...", value=st.session_state.query)
    if st.button("Submit"):
        query = st.session_state.query.strip()
        if query:
            try:
                result = st.session_state.chatbot_handler.process_query(query, st.session_state.user_email)
                st.session_state.chat_history.append({"role": "user", "content": query})
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": {
                        "message": result.get("message", "No message"),
                        "data": result.get("data", {})
                    }
                })
                st.success(result.get("message", "Done"))
                if result.get("data"):
                    st.json(result["data"])
            except Exception as e:
                st.error(f"Error: {e}")
            st.session_state.query = ""
            st.rerun()

# ===========================
# 🖥️ FRONTEND: Streamlit App
# ===========================
def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None

    if not st.session_state.authenticated:
        login_page()
        return

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=80)
        st.markdown(f"### 👤 {st.session_state.user_name}")
        st.caption(f"📧 {st.session_state.user_email}")
        st.caption(f"🧾 Role: `{st.session_state.user_role}`")
        st.markdown("---")
        if st.button("🚪 Logout"):
            for key in ['authenticated', 'user_role', 'user_name', 'user_email']:
                st.session_state[key] = False if key == 'authenticated' else None
            st.rerun()

    if st.session_state.user_role == "HR":
        hr_dashboard()
    elif st.session_state.user_role == "Manager":
        manager_dashboard()
    else:
        employee_dashboard()

    # 🧠 Speech Role Inference
    st.title("🎙️ Speech Processing and Role Inference")
    st.subheader("Upload your audio file (e.g., .wav, .mp3, .m4a)")
    audio_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "m4a"], key="audio_file_uploader")

    if audio_file is not None:
        file_name = os.path.splitext(audio_file.name)[0] + ".wav"
        audio_file_path = os.path.join("uploads", file_name)
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)

        with open(audio_file_path, "wb") as f:
            f.write(audio_file.getbuffer())

        progress = st.progress(0)
        st.write("Starting audio processing...")
        progress.progress(10)

        pipeline = SpeakerRoleInferencePipeline(audio_file_path=audio_file_path)
        st.write("Running speaker role inference pipeline...")
        progress.progress(50)

        role_mapping = pipeline.run()

        progress.progress(80)
        st.subheader("🧾 Role Mapping")
        st.json(role_mapping)

        with st.spinner("Updating speaker names in the database..."):
            try:
                response = requests.post("http://localhost:5000/process_unprocessed")
                if response.status_code == 200:
                    st.success("✅ Speaker names updated successfully in the database!")
                else:
                    st.error(f"❌ Update failed: {response.json().get('message', 'Unknown error')}")
            except Exception as e:
                st.error(f"🚫 Could not connect to backend: {str(e)}")

        progress.progress(100)
        st.success("🎉 Pipeline completed successfully!")

    # 👇 Uncomment below if you want chatbot on main page
    # chatbot_tab()

# ===========================
# 🚀 MAIN ENTRY
# ===========================
if __name__ == "__main__":
    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()
    main()
