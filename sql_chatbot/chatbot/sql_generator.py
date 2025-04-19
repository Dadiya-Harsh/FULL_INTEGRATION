from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm_config import LLMFactory
import os
from dotenv import load_dotenv

load_dotenv()

class SQLGenerator:
    """Generates SQL queries from natural language questions using LLMs."""
    
    def __init__(self, 
                 db_schema: str, 
                 llm_provider: str = "groq",
                 model_name: Optional[str] = None,
                 temperature: float = 0,
                 api_key: Optional[str] = None):
        """
        Initialize the SQL query generator.
        
        Args:
            db_schema: String representation of the database schema
            llm_provider: LLM provider ("groq", "google", "openai")
            model_name: Name of the model to use
            temperature: Temperature for LLM responses
            api_key: API key for the LLM service
        """
        self.db_schema = db_schema
        self.llm = LLMFactory.create_llm(
            provider=llm_provider,
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )
        self.parser = StrOutputParser()
        
    def create_query(self, question: str) -> str:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question about the database
            
        Returns:
            A valid SQL query string
        """
        # Create prompt template
        sql_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert SQL query generator. 
            Given the database schema below and a natural language question, generate a SQL query that correctly answers the question.
            Return ONLY the SQL query without any explanations, comments, or markdown formatting.
            
            Database Schema:
            {schema}"""),
            ("human", "{question}")
        ])
        
        # Create chain for query generation
        sql_chain = sql_prompt | self.llm | self.parser
        
        # Generate SQL query
        query = sql_chain.invoke({
            "schema": self.db_schema,
            "question": question
        })
        
        # Clean up the query (remove backticks, etc)
        query = query.strip()
        if query.startswith('```sql'):
            query = query[7:]
        if query.startswith('```'):
            query = query[3:]
        if query.endswith('```'):
            query = query[:-3]
        
        return query.strip()
        
    def generate_safe_query(self, question: str) -> tuple[str, Optional[str]]:
        """
        Generate SQL query with safety validation.
        
        Args:
            question: Natural language question about the database
            
        Returns:
            Tuple of (query, error_message) where error_message is None if successful
        """
        try:
            # Generate basic query
            query = self.create_query(question)
            
            # Security validation - ensure it's a SELECT query
            if not query.lower().strip().startswith('select'):
                return "", "For security reasons, only SELECT queries are allowed."
                
            # Check for unsafe operations
            unsafe_keywords = ['drop', 'delete', 'update', 'insert', 'alter', 'create', 
                             'truncate', 'exec', 'execute', 'xp_', 'sp_']
            
            if any(unsafe_word in query.lower() for unsafe_word in unsafe_keywords):
                return "", "Query contains potentially unsafe operations."
                
            return query, None
            
        except Exception as e:
            return "", f"Error generating SQL query: {str(e)}"