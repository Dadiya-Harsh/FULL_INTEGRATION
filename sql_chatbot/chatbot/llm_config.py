from typing import Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

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
        # Default models for each provider
        default_models = {
            "groq": "llama-3.3-70b-versatile",
            "google": "gemini-2.5-flash-preview-04-17",
            "openai": "gpt-4"
        }
        
        # Ensure model is set
        model = kwargs.get('model') or default_models.get(provider)
        if not model:
            raise ValueError(f"No model specified for provider {provider}")
            
        providers = {
            "groq": lambda: ChatGroq(
                model=model,
                temperature=kwargs.get('temperature', 0),
                api_key=kwargs.get('api_key')
            ),
            "google": lambda: ChatGoogleGenerativeAI(
                model=model,
                temperature=kwargs.get('temperature', 0),
                api_key=kwargs.get('api_key')
            ),
            "openai": lambda: ChatOpenAI(
                model=model,
                temperature=kwargs.get('temperature', 0),
                api_key=kwargs.get('api_key')
            )
        }
        
        if provider not in providers:
            raise ValueError(f"Unsupported LLM provider: {provider}")
            
        return providers[provider]()