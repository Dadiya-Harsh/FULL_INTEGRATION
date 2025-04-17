# -*- coding: utf-8 -*-
# app/main.py
import streamlit as st
from chatbot.app.auth import authenticate_user
from chatbot.app.chatbot_handler import ChatbotHandler
from chatbot.config.settings import DATABASE_URL, LLMConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sql_agent_tool import SQLAgentTool
from sql_agent_tool.models import DatabaseConfig
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(filename="chatbot.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

# Initialize database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

load_dotenv()

# Initialize sql-agent-tool
db_config = DatabaseConfig(
    drivername=os.getenv("DB_DRIVER"),
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME")
)
sql_agent = SQLAgentTool(db_config, LLMConfig)

def main():
    st.set_page_config(page_title="Chatbot App", page_icon="🤖")
    st.title("RBAC Chatbot")

    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.employee_id = None
        st.session_state.db_session = None
        st.session_state.chatbot_handler = None
        st.session_state.chat_history = []
        st.session_state.query = ""

    # Login form
    if not st.session_state.authenticated:
        st.subheader("Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            employee_id = authenticate_user(email, password)
            if employee_id:
                st.session_state.authenticated = True
                st.session_state.employee_id = employee_id
                st.session_state.db_session = SessionLocal()
                st.session_state.chatbot_handler = ChatbotHandler(
                    st.session_state.db_session, sql_agent
                )
                st.success("Login successful!")
                logging.info("Login Success..")
                st.rerun()
            else:
                st.error("Invalid credentials")
                logging.error("Invalid Credentials")
        return

    # Main chatbot interface
    st.subheader(f"Welcome, User {st.session_state.employee_id}")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                if isinstance(msg["content"], dict) and "message" in msg["content"] and "data" in msg["content"]:
                    st.write(msg["content"]["message"])
                    if msg["content"]["data"]:
                        st.write("Result Details:")
                        st.json(msg["content"]["data"])
                    else:
                        st.write("No additional data available.")
                else:
                    st.write(msg["content"])
            else:
                st.write(msg["content"])

    # Use session state to manage query input
    st.session_state.query = st.text_input("Enter your query (e.g., 'Show my tasks')", value=st.session_state.query)
    if st.button("Submit Query"):
        query = st.session_state.query.strip()
        if query:
            try:
                response = st.session_state.chatbot_handler.process_query(query, st.session_state.employee_id)
                logging.info(f"Users query: {query}")
                logging.info(f"Response: {response}")  # Debug log for full response
                
                st.session_state.chat_history.append({"role": "user", "content": query})
                
                if isinstance(response, dict) and response.get("status") == "success":
                    message = response["message"]
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": response.get("data", {})}
                    })
                    st.success(message)
                    if "data" in response and response["data"]:
                        st.write("Result Details:")
                        st.json(response["data"])
                elif isinstance(response, dict):
                    message = response.get("message", "An error occurred.")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": {}}
                    })
                    st.error(message)
                else:
                    message = "Unexpected response format."
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": {}}
                    })
                    st.error(message)
                    logging.error(f"Unexpected response: {response}")
            except Exception as e:
                message = f"Error processing query: {str(e)}"
                st.session_state.chat_history.append({"role": "user", "content": query})
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": {"message": message, "data": {}}
                })
                st.error(message)
                logging.exception("Error processing query")
            # Clear the query input
            st.session_state.query = ""
            st.rerun()

    # Logout button
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.employee_id = None
        if st.session_state.db_session:
            st.session_state.db_session.close()
        st.session_state.db_session = None
        st.session_state.chatbot_handler = None
        st.rerun()

if __name__ == "__main__":
    main()