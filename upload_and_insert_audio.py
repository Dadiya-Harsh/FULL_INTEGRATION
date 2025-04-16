

# import streamlit as st
# from app01 import employee_dashboard, hr_dashboard, login_page, manager_dashboard  # Import login page function
# from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline
# import os

# # Initialize session state variables if they don't exist
# if 'authenticated' not in st.session_state:
#     st.session_state.authenticated = False
# if 'user_name' not in st.session_state:
#     st.session_state.user_name = None
# if 'user_email' not in st.session_state:
#     st.session_state.user_email = None
# if 'user_role' not in st.session_state:
#     st.session_state.user_role = None

# def main():
#     # Check if the user is authenticated
#     if not st.session_state.authenticated:
#         login_page()  # Show the login page if the user is not authenticated
#         return  # Exit the function here to avoid showing the main content

#     # If authenticated, show the main content
#     with st.sidebar:
#         st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=80)
#         st.markdown(f"### 👤 {st.session_state.user_name}")
#         st.caption(f"📧 {st.session_state.user_email}")
#         st.caption(f"🧾 Role: `{st.session_state.user_role}`")
#         st.markdown("---")
        
#         # Logout button
#         if st.button("🚪 Logout"):
#             # Reset session state on logout
#             for key in ['authenticated', 'user_role', 'user_name', 'user_email']:
#                 st.session_state[key] = False if key == 'authenticated' else None
#             st.experimental_rerun()  # Re-run the app to navigate to login page

#     # Display the correct dashboard based on the user's role
#     if st.session_state.user_role == "HR":
#         hr_dashboard()  # Show HR dashboard
#     elif st.session_state.user_role == "Manager":
#         manager_dashboard()  # Show Manager dashboard
#     else:
#         employee_dashboard()  # Show Employee dashboard

#     # Speech Processing and Role Inference Section
#     st.title("Speech Processing and Role Inference")
#     st.subheader("Upload your audio file (e.g., .wav, .mp3, .m4a)")



#     # Create file upload widget with a unique key
#     audio_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "m4a"], key="audio_file_uploader")

#     if audio_file is not None:
#         # Extract the file name without extension and append .wav
#         file_name = os.path.splitext(audio_file.name)[0] + ".wav"
        
#         # Save the uploaded file locally with the new name
#         audio_file_path = os.path.join("uploads", file_name)
        
#         # Ensure the uploads directory exists
#         os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        
#         with open(audio_file_path, "wb") as f:
#             f.write(audio_file.getbuffer())
        
#         # Show progress bar for file processing
#         progress = st.progress(0)  # Initialize progress bar at 0%
        
#         # Step 1: Run initial setup or preprocessing
#         st.write("Starting audio processing...")
#         progress.progress(10)  # Update progress to 10%

#         # Step 2: Run the pipeline
#         pipeline = SpeakerRoleInferencePipeline(audio_file_path=audio_file_path)  # Pass the audio file path here
        
#         st.write("Running speaker role inference pipeline...")
#         progress.progress(50)  # Update progress to 50%

#         role_mapping = pipeline.run()
        
#         # Step 3: Display results
#         progress.progress(80)  # Update progress to 80%
        
#         st.subheader("Role Mapping")
#         st.json(role_mapping)
        
#         # Final step: Notify the user when processing is complete
#         progress.progress(100)  # Update progress to 100%
#         st.success("Pipeline completed successfully!")




# if __name__ == "__main__":
#     main()
# combined_app.py

import os
import requests
from flask import Flask, jsonify
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import streamlit as st

from processor import process_new_meetings
from app01 import employee_dashboard, hr_dashboard, login_page, manager_dashboard
from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline

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

    if st.session_state.user_role == "HR":
        hr_dashboard()
    elif st.session_state.user_role == "Manager":
        manager_dashboard()
    else:
        employee_dashboard()

    st.title("🎙️ Speech Processing and Role Inference")
    st.subheader("📤 Upload your audio file (e.g., .wav, .mp3, .m4a)")
    audio_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "m4a"], key="audio_file_uploader")

    # 🧠 PROCESSING (only once!)
    if audio_file is not None and not st.session_state.transcript_ready:
        file_name = os.path.splitext(audio_file.name)[0] + ".wav"
        audio_file_path = os.path.join("uploads", file_name)
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)

        with open(audio_file_path, "wb") as f:
            f.write(audio_file.getbuffer())

        with st.spinner("🔄 Processing audio and sampling utterances..."):
            st.session_state.pipeline = SpeakerRoleInferencePipeline(audio_file_path=audio_file_path)
            st.session_state.samples = st.session_state.pipeline.run_for_raw_transcript()
            st.session_state.transcript_ready = True
        st.success("✅ Audio processed successfully!")
        st.rerun()

    # 👀 PREVIEW & MANUAL SPEAKER LABELING
    if st.session_state.transcript_ready and st.session_state.samples:
        st.subheader("📝 Preview Sample Utterances")
        for s in st.session_state.samples:
            st.markdown(f"**{s['speaker']}**: {s['text']}")

        st.subheader("🔢 How many unique speakers?")
        num_speakers = st.number_input("Number of Speakers", min_value=1, max_value=10, value=2, step=1)

        st.subheader("✍️ Assign Role Labels")
        speaker_labels = {}
        for i in range(num_speakers):
            key = f"speaker_{i}"
            label = st.text_input(f"Label for {key}", value=f"Speaker {i + 1}")
            speaker_labels[key] = label

        if st.button("✅ Apply Speaker Labels"):
            with st.spinner("🔄 Mapping labels to full transcript..."):
                transcript = st.session_state.pipeline.apply_manual_labels(speaker_labels)
                st.session_state.labeled_transcript = transcript
            st.success("🎯 Speaker roles successfully applied!")

    # ✅ FINAL LABELED TRANSCRIPT
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

