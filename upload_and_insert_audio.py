import os
import requests
from processor import process_new_meetings
import streamlit as st
from flask import Flask, jsonify
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# Your app imports
from app01 import employee_dashboard, hr_dashboard, login_page, manager_dashboard
from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline
# from modules.db.process_new_meetings import process_new_meetings  # Assuming this is your logic

# ============================
# 🔁 BACKEND: Flask + Scheduler
# ============================
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
    app.run(port=5000, debug=False, use_reloader=False)  # use_reloader=False prevents double thread

def scheduled_processing():
    print("⏰ Auto-scheduler triggered.")
    try:
        process_new_meetings()
    except Exception as e:
        print(f"Scheduled processing error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_processing, trigger="interval", minutes=1)
scheduler.start()

# ============================
# 🖥️ FRONTEND: Streamlit App
# ============================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

def main():
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

    st.title("Speech Processing and Role Inference")
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
        st.subheader("Role Mapping")
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

# ========================================
# ✅ MAIN ENTRY POINT - Launch Flask thread
# ========================================
if __name__ == "__main__":
    # Start Flask app in background
    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Run Streamlit app
    main()
