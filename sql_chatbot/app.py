import os
import streamlit as st

from chatbot.langchain_bot import SQLChatbot

# Page configuration
st.set_page_config(
    page_title="SQL Database Chatbot",
    page_icon="💬",
    layout="wide"
)

import os
from dotenv import load_dotenv

load_dotenv()

# Initialize chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Initialize chatbot
@st.cache_resource
def load_chatbot():
    openai_api_key = os.getenv("GROQ_API_KEY")
    if not openai_api_key:
        st.error("Please set the OPENAI_API_KEY environment variable")
        st.stop()
    
    db_uri = os.getenv("DATABASE_URL")
    return SQLChatbot(db_uri=db_uri, openai_api_key=openai_api_key)

# Add a title
st.title("💬 Database Q&A Chatbot")
st.markdown("""
Ask questions about your company data in natural language.
Try asking:
- How many employees work in the Engineering team?
- What's the average salary in each department?
- Which project has the most hours logged?
""")

# User interface
chatbot = load_chatbot()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
user_query = st.chat_input("Ask a question about your company data")
if user_query:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    # Display user message
    with st.chat_message("user"):
        st.write(user_query)
    
    # Display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            print(f"User query: {user_query}")
            response = chatbot.process_query(user_query)
            st.write(response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})

# Add sidebar with database info
with st.sidebar:
    st.header("Database Information")
    st.markdown("""
    This chatbot connects to a company database with the following tables:
    - employees (employee info, salaries)
    - teams (departments, team info)
    - projects (project details)
    - assignments (who works on what)
    - performance (employee reviews)
    """)
    
    # Add option to view database schema
    if st.button("View Database Schema"):
        schema = chatbot.get_db_schema()
        st.code(schema)
    
    # Add option to view sample data
    if st.button("View Sample Data"):
        with st.spinner("Loading sample data..."):
            sample_data = chatbot.get_sample_data()
            for table_name, df in sample_data.items():
                st.subheader(f"Table: {table_name}")
                st.dataframe(df)