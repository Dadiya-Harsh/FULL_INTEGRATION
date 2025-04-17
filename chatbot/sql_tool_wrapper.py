import os
from dotenv import load_dotenv
from sql_agent_tool.core import SQLAgentTool
from sql_agent_tool.models import DatabaseConfig, LLMConfig
from sqlalchemy import create_engine, text
from typing import Dict, Any

load_dotenv()

class SQLToolWrapper:
    def __init__(self, role: str, email: str = None):
        # Map role to database user credentials
        role_to_credentials = {
            "employee": {
                "username": os.getenv("EMPLOYEE_DB_USER"),
                "password": os.getenv("EMPLOYEE_DB_PASSWORD")
            },
            "manager": {
                "username": os.getenv("MANAGER_DB_USER"),
                "password": os.getenv("MANAGER_DB_PASSWORD")
            },
            "hr": {
                "username": os.getenv("HR_DB_USER"),
                "password": os.getenv("HR_DB_PASSWORD")
            }            
        }
        
        if role not in role_to_credentials:
            raise ValueError(f"Invalid role: {role}")

        # Create DatabaseConfig
        db_config = DatabaseConfig(
            drivername="postgresql",
            username=role_to_credentials[role]["username"],
            password=role_to_credentials[role]["password"],
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME")
        )

        # Create LLMConfig
        llm_config = LLMConfig(
            provider="groq",
            api_key=os.getenv("GROQ_API_KEY"),
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1000
        )

        # Initialize SQLAgentTool
        self.tool = SQLAgentTool(db_config, llm_config, max_rows=1000, read_only=True)

        # Set app.current_user for RLS if email provided
        if email:
            engine = create_engine(
                f"postgresql://{role_to_credentials[role]['username']}:{role_to_credentials[role]['password']}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
            )
            with engine.connect() as conn:
                conn.execute(text("SET app.current_name = :email"), {"email": email})
                conn.commit()

    def process_natural_language(self, query: str) -> Dict[str, Any]:
        try:
            result = self.tool.process_natural_language_query(query)
            
            if result.success:
                return {
                    "success": True,
                    "data": result.data,
                    "columns": result.columns,
                    "row_count": result.row_count
                }
            else:
                return {
                    "success": False,
                    "error": result.error
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }