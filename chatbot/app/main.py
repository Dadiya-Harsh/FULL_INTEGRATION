# -*- coding: utf-8 -*-
# app/main.py
import streamlit as st
import os
import sys

# Add chatbot directory to sys.path if not already present
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.app.auth import authenticate_user
from chatbot.app.langgraph_workflow import initialize_workflow
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from dotenv import load_dotenv

logging.basicConfig(filename="chatbot.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

# Initialize database
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/yourdb")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def main():
    st.set_page_config(page_title="Chatbot App", page_icon="🤖")
    st.title("RBAC Chatbot")

    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.employee_id = None
        st.session_state.db_session = None
        st.session_state.chat_history = []
        st.session_state.query = ""
        st.session_state.workflow = None

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
                st.session_state.workflow = initialize_workflow(st.session_state.employee_id, DATABASE_URL)
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
                # Invoke the LangGraph workflow
                response = st.session_state.workflow.invoke({
                    "messages": [{"role": "user", "content": query}],
                    "employee_id": st.session_state.employee_id
                })
                
                content = response["messages"][-1]["content"]
                st.session_state.chat_history.append({"role": "user", "content": query})
                
                if isinstance(content, dict) and content.get("status") == "success":
                    message = content["message"]
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": content.get("data", {})}
                    })
                    st.success(message)
                    if "data" in content and content["data"]:
                        st.write("Result Details:")
                        st.json(content["data"])
                elif isinstance(content, dict):
                    message = content.get("message", "An error occurred.")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": {}}
                    })
                    st.error(message)
                else:
                    message = str(content) if content else "Unexpected response format."
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": {"message": message, "data": {}}
                    })
                    st.error(message)
                    logging.error(f"Unexpected response: {content}")
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
        st.session_state.workflow = None
        st.rerun()

if __name__ == "__main__":
    main()