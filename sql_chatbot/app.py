import streamlit as st
import logging
from pathlib import Path
import sys

# Add project root to Python path dynamically
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from chatbot.langchain_bot import SQLChatbot
import os
from dotenv import load_dotenv
load_dotenv()

# Modify log file path to be relative to project root
logging.basicConfig(
    filename=project_root / 'chatbot/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize chatbot
DB_URI = os.getenv("DATABASE_URL") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
chatbot = SQLChatbot(
    db_uri=DB_URI, 
    api_key=GEMINI_API_KEY,
    # model_name="llama-3.3-70b-versatile",  # Specify default model
    llm_provider="google"
)

# Streamlit app
st.title("SQL Chatbot with RBAC")

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'email' not in st.session_state:
    st.session_state.email = ""

# Email input
email = st.text_input("Enter your email:", value=st.session_state.email)
if email:
    st.session_state.email = email

# Chat interface
st.subheader("Chat with the Bot")
user_query = st.text_input("Ask a question about the database:")
if user_query and email:
    try:
        with st.chat_message("user"):
            st.write(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                logger.info(f"User query: {user_query} by {email}")
                response = chatbot.process_query(user_query, email)
                st.write(response)
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
    except Exception as e:
        st.error(f"Error: {str(e)}")
        logger.error(f"Error processing query: {str(e)}")

# Display chat history
st.subheader("Chat History")
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Display schema and sample data
if st.button("Show Database Schema"):
    schema = chatbot.get_db_schema()
    st.write("### Database Schema")
    st.text(schema)

if st.button("Show Sample Data"):
    sample_data = chatbot.get_sample_data()
    for table, df in sample_data.items():
        st.write(f"### {table}")
        st.dataframe(df)