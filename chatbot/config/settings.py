# -*- coding: utf-8 -*-
# config/settings.py
import os
from dotenv import load_dotenv
from sql_agent_tool.models import LLMConfig

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@19.168.10.74:5433/testdb")
GROQ_API_KEY = os.getenv("GEMINI_API_KEY", "your-api-key")

LLMConfig = LLMConfig(
    provider="gemini",
    api_key=GROQ_API_KEY,
    model="models/gemini-1.5-flash",
)
