# -*- coding: utf-8 -*-
# config/settings.py
import os
from dotenv import load_dotenv
from sql_agent_tool.models import LLMConfig

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/test_sentiment_analysis")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your-api-key")

LLMConfig = LLMConfig(
    provider="groq",
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    max_tokens=500
)
