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

# Initialize database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Initialize sql-agent-tool
db_config = DatabaseConfig(
    drivername="postgresql",
    username="postgres",  # Loaded from .env in production
    password="password",
    host="192.168.10.74",
    port=5433,
    database="test1"
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
                st.rerun()
            else:
                st.error("Invalid credentials")
        return

    # Main chatbot interface
    st.subheader(f"Welcome, User {st.session_state.employee_id}")
    query = st.text_input("Enter your query (e.g., 'Show my tasks')")
    if st.button("Submit Query"):
        if query:
            response = st.session_state.chatbot_handler.process_query(
                query, st.session_state.employee_id
            )
            if response["status"] == "success":
                st.success(response["message"])
                st.json(response["data"])
            else:
                st.error(response["message"])
        else:
            st.warning("Please enter a query")

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
