import json
import logging
import os
import requests
from flask import Flask, jsonify
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
# from chatbot.app.chatbot_handler import ChatbotHandler
from modules.db.models import Employee
from modules.sentiment_analysis.utils import chunk_and_summarize_text, fetch_all_employees, validate_speaker_roles_with_llm
import streamlit as st

from modules.sentiment_analysis.processor import process_new_meetings
from Dashboard import SessionLocal, employee_dashboard, get_employee_by_email, hr_dashboard, login_page, manager_dashboard
from modules.pipelines.speaker_role_inference import SpeakerRoleInferencePipeline
# from chatbot.app.main import sql_agent

# Import the SQLChatbot
from sql_chatbot.chatbot.langchain_bot import SQLChatbot
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def safe_print(*args, **kwargs):
    try:
        if sys.stdout and not sys.stdout.closed:
            print(*args, **kwargs)
    except Exception:
        pass

logging.basicConfig(filename="chatbot.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

# ============================
# 🔁 BACKEND: Flask + Scheduler
# ============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Flask backend is running!"

def start_flask():
    app.run(port=5000, debug=False, use_reloader=False)

# ============================
# 🖥️ FRONTEND: Streamlit App
# ============================

# Initialize all session state variables
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'login_email' not in st.session_state:  # Added login_email
        st.session_state.login_email = None
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
    # Chatbot specific state
    if 'chatbot_authenticated' not in st.session_state:
        st.session_state.chatbot_authenticated = False
    if 'db_session' not in st.session_state:
        st.session_state.db_session = None
    if 'chatbot_handler' not in st.session_state:
        st.session_state.chatbot_handler = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'query' not in st.session_state:
        st.session_state.query = ""
    if 'employee_id' not in st.session_state:
        st.session_state.employee_id = None
    # SQL Chatbot integration
    if 'sql_chatbot' not in st.session_state:
        st.session_state.sql_chatbot = None

def format_transcript_to_markdown(transcript):
    """Convert transcript entries to HTML with bold speaker names"""
    html_lines = []
    for entry in transcript:
        speaker = entry['speaker']
        text = entry['text']
        html_lines.append(f"<strong>{speaker}</strong>: {text}")
    return "<br>".join(html_lines)

# ============================
# 🤖 CHATBOT TAB
# ============================
def init_sql_chatbot():
    """Initialize the SQL chatbot if not already done"""
    try:
        DB_URI = os.getenv("DATABASE_URL")
        LLM_API_KEY = os.getenv("GROQ_API_KEY")
        
        # Initialize the SQLChatbot
        chatbot = SQLChatbot(
            db_uri=DB_URI, 
            api_key=LLM_API_KEY,
            llm_provider="groq"  # You can change to "groq" based on available API keys
        )
        return chatbot
    except Exception as e:
        logging.error(f"Failed to initialize SQL chatbot: {str(e)}")
        return None

def chatbot_tab():
    st.title("🤖 SQL Chatbot with RBAC")
    
    # Initialize SQL chatbot if not already done
    if st.session_state.sql_chatbot is None:
        with st.spinner("Initializing chatbot..."):
            st.session_state.sql_chatbot = init_sql_chatbot()
            if st.session_state.sql_chatbot is None:
                st.error("Failed to initialize the SQL chatbot. Please check the logs.")
                return
    
    # Check if user is authenticated
    if not st.session_state.authenticated or not st.session_state.user_email:
        st.warning("Please login to use the chatbot")
        return
    
    st.subheader(f"Welcome, {st.session_state.user_name}")
    
    # Display chat history
    for i, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Chat input
    query = st.chat_input("Ask a question about the database:", key="sql_chat_input")
    
    if query:
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": query})
        
        # Display user message
        with st.chat_message("user"):
            st.write(query)
        
        # Process query
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.sql_chatbot.process_query(query, st.session_state.user_email)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                
                # Display assistant response
                with st.chat_message("assistant"):
                    st.write(response)
            except Exception as e:
                error_message = f"Error: {str(e)}"
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})
                with st.chat_message("assistant"):
                    st.error(error_message)
                logging.exception("Query failed")


def main():
    init_session_state()  # Initialize all session state variables
    
    if not st.session_state.authenticated:
        login_page()
        return

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=80)
        st.markdown(f"### 👤 {st.session_state.user_name}")
        st.caption(f"📧 {st.session_state.user_email}")
        st.caption(f"🧾 Role: `{st.session_state.user_role}`")
        st.markdown("---")
        if st.button("🚪 Logout", key="logout_button"):
            # Reset all session state on logout
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📤 Upload Meeting", "💬 SQL Chatbot"])

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

            max_per_speaker = st.slider(
                "Number of samples per speaker",
                min_value=1,
                max_value=5,
                value=3,
                help="Adjust the number of utterances to show for each speaker",
                key="samples_slider"
            )

            if st.button("🔄 Refresh Samples", key="refresh_samples_button"):
                with st.spinner("Resampling utterances..."):
                    if st.session_state.pipeline and st.session_state.pipeline.transcript:
                        st.session_state.samples = st.session_state.pipeline.sample_utterances(
                            st.session_state.pipeline.transcript,
                            max_per_speaker=max_per_speaker
                        )
                st.success("✅ Samples updated!")
                st.rerun()

            st.subheader("🔢 Detected Speakers")
            if st.session_state.transcript_ready:
                st.info(f"Detected {st.session_state.num_speakers} unique speakers in the audio")

            st.subheader("✍️ Assign Role Labels")

            employees = fetch_all_employees()
            num_speakers = st.session_state.num_speakers if "num_speakers" in st.session_state else 2

            if "llm_suggestions" not in st.session_state:
                st.session_state.llm_suggestions = {}

            if st.button("🤖 Suggest Speaker Names using LLM", key="llm_suggest_button"):
                with st.spinner("LLM is analyzing transcript..."):
                    raw_transcript_text = "\n".join([f"{s['speaker']}: {s['text']}" for s in st.session_state.samples])
                    llm_output = validate_speaker_roles_with_llm(raw_transcript_text, allowed_names=employees)
                    llm_suggestions = json.loads(llm_output)["suggested_labels"]
                    llm_suggestions = {k: v for k, v in llm_suggestions.items() if v in employees}
                    
                    unique_speakers = sorted(set(s["speaker"] for s in st.session_state.samples))
                    normalized_suggestions = {}
                    assigned_names = set()

                    for i, speaker in enumerate(unique_speakers):
                        key = f"speaker_{i}"
                        suggestion_key = speaker.lower().replace(" ", "_")
                        if suggestion_key in llm_suggestions and llm_suggestions[suggestion_key] in employees:
                            name = llm_suggestions[suggestion_key]
                        else:
                            available = [emp for emp in employees if emp not in assigned_names]
                            name = available[0] if available else "Unknown"
                        normalized_suggestions[key] = name
                        assigned_names.add(name)

                    st.session_state.llm_suggestions = normalized_suggestions
                st.success("✅ Suggestions ready below!")

            if st.session_state.llm_suggestions:
                st.markdown("### 🧠 LLM Suggested Labels:")
                for speaker, name in st.session_state.llm_suggestions.items():
                    st.markdown(f"- **{speaker}** → 🧠 `{name}`")
                st.info("These names are pre-filled in the dropdowns below. You can adjust them manually.")

            st.markdown("### ✍️ Assign Roles to Speakers")
            selected_employees = []
            speaker_labels = {}

            for i in range(num_speakers):
                key = f"speaker_{i}"
                available_options = [emp for emp in employees if emp not in selected_employees]
                default_selection = st.session_state.llm_suggestions.get(key, None)
                if default_selection not in available_options:
                    default_selection = None

                selected = st.selectbox(
                    f"Select employee for {key}",
                    options=available_options,
                    index=available_options.index(default_selection) if default_selection else 0,
                    key=f"select_{key}"
                )
                speaker_labels[key] = selected
                selected_employees.append(selected)

            if st.button("✅ Apply Speaker Labels", key="apply_labels_button"):
                with st.spinner("🔄 Mapping labels to full transcript..."):
                    transcript = st.session_state.pipeline.apply_manual_labels(speaker_labels)
                    st.session_state.labeled_transcript = transcript
                st.success("🎯 Speaker roles successfully applied!")

        if st.session_state.labeled_transcript:
            st.subheader("🗒️ Final Transcript with Labels")
            
            with st.expander("📜 View Full Transcript", expanded=True):
                formatted_md = format_transcript_to_markdown(st.session_state.labeled_transcript)
                st.markdown(
                    f"""
                    <div style="height:300px; overflow-y:auto; padding:10px; background-color:#f9f9f9; border:1px solid #ccc;">
                        <div style="font-size: 15px; line-height: 1.6;">
                            {formatted_md}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("📥 Save to Database", key="save_db_button"):
                    with st.spinner("💾 Saving transcript..."):
                        st.session_state.pipeline.insert_to_db(st.session_state.labeled_transcript)
                        st.success("✅ Transcript saved to database!")
                        with st.spinner("⚙️ Processing meeting metrics..."):
                            result = process_new_meetings()
                            if "error" in result:
                                st.error(f"❌ Processing failed: {result['error']}")
                            else:
                                st.success("✅ Analysis complete!")
            
            with col3:
                if st.button("🔄 Start Over", key="start_over_button"):
                    for key in ["pipeline", "samples", "transcript_ready", "labeled_transcript"]:
                        st.session_state[key] = None if key == "pipeline" else False if key == "transcript_ready" else None
                    st.rerun()

    with tab3:
        chatbot_tab()

if __name__ == "__main__":
    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()
    main()