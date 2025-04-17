
import json
import os
import requests
from flask import Flask, jsonify
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from modules.sentiment_analysis.utils import chunk_and_summarize_text, fetch_all_employees, validate_speaker_roles_with_llm
import streamlit as st

from modules.sentiment_analysis.processor import process_new_meetings
from Dashboard import employee_dashboard, hr_dashboard, login_page, manager_dashboard
from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline


import sys

def safe_print(*args, **kwargs):
    try:
        if sys.stdout and not sys.stdout.closed:
            print(*args, **kwargs)
    except Exception:
        pass

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
    app.run(port=5000, debug=False, use_reloader=False)

# def scheduled_processing():
#     print("⏰ Auto-scheduler triggered.")
#     try:
#         process_new_meetings()
#     except Exception as e:
#         print(f"Scheduled processing error: {e}")


def scheduled_processing():
    safe_print("⏰ Auto-scheduler triggered.")
    try:
        process_new_meetings()
    except Exception as e:
        safe_print(f"Scheduled processing error: {e}")

# scheduler = BackgroundScheduler()
# scheduler.add_job(func=scheduled_processing, trigger="interval", minutes=1)
# scheduler.start()


scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scheduled_processing,
    trigger='interval',
    minutes=1,
    max_instances=1,
    misfire_grace_time=30  # Optionally skip jobs that fall behind
)
scheduler.start()



# ============================
# 🖥️ FRONTEND: Streamlit App
# ============================

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if 'pipeline' not in st.session_state:
    st.session_state.pipeline = None
if 'samples' not in st.session_state:
    st.session_state.samples = None
if 'transcript_ready' not in st.session_state:
    st.session_state.transcript_ready = False
if 'labeled_transcript' not in st.session_state:
    st.session_state.labeled_transcript = None


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

    tab1, tab2 = st.tabs(["📊 Dashboard", "📤 Upload Meeting"])

    with tab1:
        if st.session_state.user_role == "HR":
            hr_dashboard()
        elif st.session_state.user_role == "Manager":
            manager_dashboard()
        else:
            employee_dashboard()

    with tab2:
        st.title("🎙️ Speech Processing and Role Inference")
        st.subheader("📤 Upload your audio file (e.g., .wav, .mp3, .m4a)")
        audio_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "m4a"], key="audio_file_uploader")

        if audio_file is not None and not st.session_state.transcript_ready:
            file_name = os.path.splitext(audio_file.name)[0] + ".wav"
            audio_file_path = os.path.join("uploads", file_name)
            os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)

            with open(audio_file_path, "wb") as f:
                f.write(audio_file.getbuffer())

            with st.spinner("🔄 Processing audio and sampling utterances..."):
                st.session_state.pipeline = SpeakerRoleInferencePipeline(audio_file_path=audio_file_path)
                st.session_state.samples, st.session_state.num_speakers = st.session_state.pipeline.run_for_raw_transcript()
                st.session_state.transcript_ready = True
            st.success("✅ Audio processed successfully!")
            st.rerun()

        if st.session_state.transcript_ready and st.session_state.samples:
            st.subheader("📝 Preview Sample Utterances")

            for s in st.session_state.samples:
                st.markdown(f"**{s['speaker']}**: {s['text']}")

            if st.button("🔄 Refresh Samples"):
                with st.spinner("Resampling utterances..."):
                    st.session_state.samples, _ = st.session_state.pipeline.run_for_raw_transcript()
                st.success("✅ Samples updated!")
                st.rerun()

            st.subheader("🔢 Detected Speakers")
            if st.session_state.transcript_ready:
                st.info(f"Detected {st.session_state.num_speakers} unique speakers in the audio")

            st.subheader("✍️ Assign Role Labels")

            employees = fetch_all_employees()
            num_speakers = st.session_state.num_speakers if "num_speakers" in st.session_state else 2

            # Init suggestion store
            if "llm_suggestions" not in st.session_state:
                st.session_state.llm_suggestions = {}

            # Step 1: Get LLM suggestions
            if st.button("🤖 Suggest Speaker Names using LLM"):
                with st.spinner("LLM is analyzing transcript..."):
                    raw_transcript_text = "\n".join([f"{s['speaker']}: {s['text']}" for s in st.session_state.samples])
                    # summarized_transcript = chunk_and_summarize_text(raw_transcript_text)

                    llm_output = validate_speaker_roles_with_llm(raw_transcript_text)
                    llm_suggestions = json.loads(llm_output)["suggested_labels"]
                    # Normalize keys to match the format "speaker_0", "speaker_1"

                    # llm_suggestions = {k.lower().replace(" ", "_"): v for k, v in llm_suggestions.items()}
                    # st.session_state.llm_suggestions = llm_suggestions
                    unique_speakers = sorted(set(s["speaker"] for s in st.session_state.samples))

        # Create a mapping from normalized speaker IDs to suggested names
                    normalized_suggestions = {}
                    for i, speaker in enumerate(unique_speakers):
                        key = f"speaker_{i}"
                        if speaker.lower().replace(" ", "_") in llm_suggestions:
                            normalized_suggestions[key] = llm_suggestions[speaker.lower().replace(" ", "_")]

                    st.session_state.llm_suggestions = normalized_suggestions

                st.success("✅ Suggestions ready below!")

            # Step 2: Show LLM suggestions (if available)
            if st.session_state.llm_suggestions:
                st.markdown("### 🧠 LLM Suggested Labels:")
                for speaker, name in st.session_state.llm_suggestions.items():
                    st.markdown(f"- **{speaker}** → 🧠 `{name}`")
                st.info("These names are pre-filled in the dropdowns below. You can adjust them manually.")

            # Step 3: Manual dropdowns (pre-filled)
            st.markdown("### ✍️ Assign Roles to Speakers")
            selected_employees = []
            speaker_labels = {}

            for i in range(num_speakers):  # Use the defined variable instead
                key = f"speaker_{i}"
                available_options = [emp for emp in employees if emp not in selected_employees]

                if not available_options:
                    st.warning("No more available employees to assign.")
                    break

                selected = st.selectbox(
                    f"Select employee for {key}", available_options, key=f"select_{key}"
                )
                speaker_labels[key] = selected
                selected_employees.append(selected)

            if st.button("✅ Apply Speaker Labels"):
                with st.spinner("🔄 Mapping labels to full transcript..."):
                    transcript = st.session_state.pipeline.apply_manual_labels(speaker_labels)
                    st.session_state.labeled_transcript = transcript
                st.success("🎯 Speaker roles successfully applied!")

        if st.session_state.labeled_transcript:
            st.subheader("🗒️ Final Transcript with Labels")
            for entry in st.session_state.labeled_transcript:
                st.markdown(f"**{entry['speaker']}** [{entry['start']:.2f}s - {entry['end']:.2f}s]: {entry['text']}")

            if st.button("📥 Save to Database"):
                with st.spinner("💾 Saving transcript..."):
                    st.session_state.pipeline.insert_to_db(st.session_state.labeled_transcript)
                    st.success("✅ Transcript saved to database!")

            if st.button("🔄 Start Over"):
                for key in ["pipeline", "samples", "transcript_ready", "labeled_transcript"]:
                    st.session_state[key] = None if key == "pipeline" else False if key == "transcript_ready" else None
                st.rerun()

# ========================================
# ✅ MAIN ENTRY POINT - Launch Flask thread
# ========================================
if __name__ == "__main__":
    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()
    main()
