from typing import Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class LLMFactory:
    """Factory class for creating LLM instances."""
    
    @staticmethod
    def create_llm(provider: str = "groq", **kwargs) -> BaseLanguageModel:
        """
        Create an LLM instance based on the specified provider.
        
        Args:
            provider: The LLM provider ("groq", "google", "openai")
            **kwargs: Additional arguments for the specific LLM
        
        Returns:
            BaseLanguageModel: The configured LLM instance
        """
        groq_api_key = os.getenv("GROQ_API_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-pro")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        providers = {
            "groq": lambda: ChatGroq(
                model=groq_model,
                temperature=kwargs.get('temperature', 0),
                api_key=groq_api_key
            ),
            "google": lambda: ChatGoogleGenerativeAI(
                model=gemini_model,
                temperature=kwargs.get('temperature', 0),
                api_key=gemini_api_key
            ),
            "openai": lambda: ChatOpenAI(
                model=openai_model,
                temperature=kwargs.get('temperature', 0),
                api_key=openai_api_key
            )
        }
        
        if provider not in providers:
            raise ValueError(f"Unsupported LLM provider: {provider}")
            
        return providers[provider]()
