# -*- coding: utf-8 -*-
# app/main.py
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
