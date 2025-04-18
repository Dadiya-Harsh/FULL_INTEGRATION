from typing import List, Dict, Optional
import json
import logging
import re
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import pandas as pd
from sqlalchemy.sql import text

from chatbot.llm_config import LLMFactory

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log_file_path = Path('/home/voldemort/Integration/FULL_INTEGRATION/sql_chatbot/chatbot/chatbot.log')
log_file_path.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.info("Chatbot initialized")

class ChatState:
    """State for the chatbot conversation."""
    def __init__(
        self,
        messages: List[BaseMessage] = None,
        current_query: str = None,
        query_result: str = None,
        error: str = None,
        response: str = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        email: Optional[str] = None
    ):
        self.messages = messages or []
        self.current_query = current_query
        self.query_result = query_result
        self.error = error
        self.response = response
        self.user_id = user_id
        self.role = role
        self.email = email

    def to_dict(self):
        """Convert state to dictionary format expected by LangGraph."""
        messages_dict = []
        for msg in self.messages:
            if isinstance(msg, HumanMessage):
                messages_dict.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages_dict.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                messages_dict.append({"role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id})
            elif isinstance(msg, SystemMessage):
                messages_dict.append({"role": "system", "content": msg.content})
            else:
                logger.warning(f"Unsupported message type in to_dict: {type(msg)}")
        logger.debug(f"Serialized messages: {messages_dict}")
        return {
            "messages": messages_dict,
            "current_query": self.current_query,
            "query_result": self.query_result,
            "error": self.error,
            "response": self.response,
            "user_id": self.user_id,
            "role": self.role,
            "email": self.email
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatState':
        """Create ChatState from dictionary."""
        if isinstance(data, ChatState):
            logger.debug("Received ChatState object, returning as-is")
            return data
        if not isinstance(data, dict):
            logger.error(f"Expected dict, got {type(data)}: {data}")
            raise ValueError(f"Expected dict, got {type(data)}")
        logger.debug(f"Input data to from_dict: {data}")
        messages = []
        for msg in data.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")
            if not role or content is None:
                logger.error(f"Invalid message format: {msg}")
                raise ValueError(f"Message missing role or content: {msg}")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id is None:
                    logger.error(f"Missing tool_call_id for tool message: {msg}")
                    raise ValueError("Tool message requires tool_call_id")
                messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))
            elif role == "system":
                messages.append(SystemMessage(content=content))
            else:
                logger.error(f"Unsupported role in from_dict: {role}")
                raise ValueError(f"Unsupported message role: {role}")
        logger.debug(f"Deserialized messages: {[str(m) for m in messages]}")
        return cls(
            messages=messages,
            current_query=data.get("current_query"),
            query_result=data.get("query_result"),
            error=data.get("error"),
            response=data.get("response"),
            user_id=data.get("user_id"),
            role=data.get("role"),
            email=data.get("email")
        )

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the state."""
        if not isinstance(message, BaseMessage):
            logger.error(f"Invalid message type: {type(message)}")
            raise ValueError(f"Expected BaseMessage, got {type(message)}")
        logger.info(f"Adding message: {message.content} (type: {type(message).__name__})")
        self.messages.append(message)

class SQLChatbot:
    def __init__(self, 
                 db_uri: str, 
                 llm_provider: str = "groq",
                 model_name: Optional[str] = None,
                 temperature: float = 0,
                 api_key: Optional[str] = None):
        """Initialize the SQL chatbot.
        
        Args:
            db_uri: Database connection URI
            llm_provider: LLM provider ("groq", "google", "openai")
            model_name: Name of the model to use
            temperature: Temperature for LLM responses
            api_key: API key for the LLM service
        """
        self.llm = LLMFactory.create_llm(
            provider=llm_provider,
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )
        self.db = SQLDatabase.from_uri(db_uri)
        self.sql_tool = QuerySQLDataBaseTool(db=self.db)
        self.db_schema = self.db.get_table_info()
        logger.info(f"Database tables: {self.db.get_usable_table_names()}")
        self.workflow = self._build_graph()
        logger.info(f"SQLChatbot initialized with {llm_provider} LLM")

    def _get_user_info(self, email: str) -> tuple[int, str]:
        """Fetch user_id and role by inferring table and columns from schema."""
        try:
            # Prompt LLM to identify table and columns
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert database analyst.
                Given the database schema and an email, identify the tables and columns to fetch user identification (e.g., id, user_id) and role (e.g., role, name).
                The role may be in a separate table (e.g., role) linked via a join table (e.g., user_role).
                Return a single JSON object with:
                - table: The main table with email (e.g., employee).
                - id_column: The column for user identification (e.g., id).
                - role_table: The table with role info (e.g., role).
                - role_column: The column for role (e.g., name).
                - join_table: The table linking main and role tables (e.g., user_role).
                - join_column: The column in join_table referencing role_table (e.g., role_id).
                - main_join_column: The column in join_table referencing table (e.g., employee_id).
                If no join is needed (role is in main table), set role_table, join_table, join_column, main_join_column to empty strings.
                Return only the JSON object, no additional text.

                Database Schema:
                {schema}"""),
                ("human", "Email: {email}"),
            ])
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke({"schema": self.db_schema, "email": email})
            logger.debug(f"LLM table inference response: {response}")

            # Extract JSON from response (handle mixed text)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.error(f"No JSON found in LLM response: {response}")
                raise ValueError("No JSON in LLM response")
            json_str = json_match.group(0)
            try:
                table_info = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {json_str}, error: {str(e)}")
                raise ValueError("Invalid JSON format")

            required_keys = ['table', 'id_column', 'role_table', 'role_column', 'join_table', 'join_column', 'main_join_column']
            if not all(key in table_info for key in required_keys):
                logger.error(f"Missing keys in table_info: {table_info}")
                raise ValueError("Incomplete table information")

            table = table_info['table']
            id_column = table_info['id_column']
            role_table = table_info['role_table']
            role_column = table_info['role_column']
            join_table = table_info['join_table']
            join_column = table_info['join_column']
            main_join_column = table_info['main_join_column']

            # Build query based on whether join is needed
            if not role_table and not join_table:
                # Role is in main table
                query = text(f"SELECT {id_column}, {role_column} FROM {table} WHERE email = :email")
            else:
                # Join with role and user_role tables
                query = text(
                    f"SELECT {table}.{id_column}, {role_table}.{role_column} "
                    f"FROM {table} "
                    f"JOIN {join_table} ON {table}.{id_column} = {join_table}.{main_join_column} "
                    f"JOIN {role_table} ON {join_table}.{join_column} = {role_table}.{id_column} "
                    f"WHERE {table}.email = :email"
                )

            with self.db._engine.connect() as conn:
                result = conn.execute(query, {"email": email}).fetchall()
            logger.debug(f"Raw query result: {result}")

            if not result:
                logger.error(f"User not found for email: {email}")
                raise ValueError(f"User not found: {email}")
            if len(result) != 1:
                logger.error(f"Multiple users found for email: {email}, result: {result}")
                raise ValueError(f"Multiple users found for email: {email}")

            user_data = result[0]
            user_id, role = user_data
            if not isinstance(user_id, int) or not isinstance(role, str):
                logger.error(f"Invalid user_id or role type: user_id={type(user_id)}, role={type(role)}")
                raise ValueError(f"Invalid user_id or role type")
            logger.info(f"User {email} identified: user_id={user_id}, role={role}")
            return user_id, role
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            raise

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(dict)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("format_response", self._format_response)
        workflow.add_edge("generate_sql", "execute_sql")
        workflow.add_edge("execute_sql", "format_response")
        workflow.add_edge("format_response", END)
        workflow.set_entry_point("generate_sql")
        return workflow.compile()

    def _generate_sql(self, state: Dict) -> Dict:
        """Generate SQL query with role-based filters."""
        if not isinstance(state, dict):
            logger.error(f"Expected dict, got {type(state)}")
            raise ValueError(f"Expected dict, got {type(state)}")
        logger.debug(f"Generate SQL input state: {state}")
        chat_state = ChatState.from_dict(state)
        try:
            if not chat_state.messages:
                logger.error(f"No messages in state: {chat_state.messages}")
                raise ValueError("No messages found in state")
            if not isinstance(chat_state.messages[-1], BaseMessage):
                logger.error(f"Last message is not a BaseMessage: {chat_state.messages[-1]}")
                raise ValueError("Invalid message type in state")
            question = chat_state.messages[-1].content
            role = chat_state.role
            user_id = chat_state.user_id
            sql_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert SQL query generator.
                Given the database schema, user role, user ID, and a question, generate a SQL query that answers the question.
                Strictly adhere to the schema, using exact table and column names.
                Apply role-based access filters:
                - Employee: Filter to own records (e.g., employee.id = {user_id}).
                - Manager: Filter to team records (e.g., employee.department_id = (SELECT department_id FROM employee WHERE id = {user_id})).
                - HR: No filters.
                Use joins if needed (e.g., employee, user_role, role for role info).
                Return only the SQL query as plain text, without Markdown, code fences (```), semicolons, or multiple statements.

                User Role: {role}
                User ID: {user_id}
                Database Schema:
                {schema}"""),
                MessagesPlaceholder(variable_name="messages"),
            ])
            sql_chain = sql_prompt | self.llm | StrOutputParser()
            query = sql_chain.invoke({
                "schema": self.db_schema,
                "role": role,
                "user_id": user_id,
                "messages": chat_state.messages
            })
            # Strip any Markdown or code fences
            query = re.sub(r'```(?:sql)?\n?|\n?```', '', query).strip()
            chat_state.add_message(AIMessage(content=query))
            chat_state.current_query = query
            logger.debug(f"Generated SQL query: {query}")
            return chat_state.to_dict()
        except Exception as e:
            error_message = f"Error generating SQL query: {str(e)}"
            chat_state.add_message(AIMessage(content=error_message))
            chat_state.error = error_message
            logger.error(error_message)
            return chat_state.to_dict()

    def _execute_sql(self, state: Dict) -> Dict:
        """Execute SQL query against the database."""
        if not isinstance(state, dict):
            logger.error(f"Expected dict, got {type(state)}")
            raise ValueError(f"Expected dict, got {type(state)}")
        logger.debug(f"Execute SQL input state: {state}")
        chat_state = ChatState.from_dict(state)
        current_query = chat_state.current_query
        error = chat_state.error
        if error or not current_query:
            logger.warning(f"Skipping SQL execution due to error or no query: error={error}, query={current_query}")
            return chat_state.to_dict()
        # Validate query to ensure no Markdown
        if '```' in current_query:
            error_message = "Invalid SQL query: contains Markdown code fences"
            chat_state.add_message(AIMessage(content=error_message))
            chat_state.error = error_message
            logger.error(error_message)
            return chat_state.to_dict()
        try:
            result = self.sql_tool.invoke({"query": current_query})
            if isinstance(result, str) and result.startswith('[') and result.endswith(']'):
                try:
                    data = json.loads(result)
                    if isinstance(data, list) and data:
                        result = "\n".join([str(row) for row in data[:10]])
                        if len(data) > 10:
                            result += f"\n... (showing first 10 of {len(data)} rows)"
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse query result as JSON: {result}")
            result = str(result)
            logger.debug(f"SQL execution result: {result}")
            chat_state.add_message(AIMessage(content=result))
            chat_state.query_result = result
            # Log action to access_log
            self._log_access(chat_state, current_query, success=True)
            return chat_state.to_dict()
        except Exception as e:
            error_message = f"Error executing SQL query: {str(e)}"
            chat_state.add_message(AIMessage(content=error_message))
            chat_state.error = error_message
            logger.error(error_message)
            self._log_access(chat_state, current_query, success=False, error=str(e))
            return chat_state.to_dict()

    def _log_access(self, chat_state: ChatState, query: str, success: bool, error: Optional[str] = None):
        """Log query execution to access_log."""
        try:
            log_query = """
            INSERT INTO access_log (user_id, action, resource_type, success, error)
            VALUES (%s, %s, %s, %s, %s)
            """
            resource_type = "unknown"
            if "employee" in query.lower():
                resource_type = "employees"
            elif "access_log" in query.lower():
                resource_type = "access_log"
            self.db.run(log_query, parameters=(
                chat_state.user_id,
                "query",
                resource_type,
                success,
                error
            ))
            logger.info(f"Logged access: user_id={chat_state.user_id}, resource={resource_type}, success={success}")
        except Exception as e:
            logger.error(f"Failed to log access: {str(e)}")

    def _format_response(self, state: Dict) -> Dict:
        """Format SQL results into natural language response."""
        if not isinstance(state, dict):
            logger.error(f"Expected dict, got {type(state)}")
            raise ValueError(f"Expected dict, got {type(state)}")
        logger.debug(f"Format response input state: {state}")
        chat_state = ChatState.from_dict(state)
        messages = chat_state.messages
        current_query = chat_state.current_query
        query_result = chat_state.query_result
        error = chat_state.error
        response_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful database assistant.
            Given a user question, SQL query, query result, user role, and any error, provide a clear and helpful response.
            Respect the user's role-based access:
            - Employee: Can only see their own data.
            - Manager: Can see their team's data.
            - HR: Can see all data.
            If there was an error, explain it in a friendly manner and suggest a fix if possible.
            If the query was successful, summarize the results and directly answer the user's question.

            User Role: {role}"""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", """
            SQL query: {query}
            Query result: {result}
            Error (if any): {error}
            Please provide a helpful response:""")
        ])
        response_chain = response_prompt | self.llm | StrOutputParser()
        try:
            response = response_chain.invoke({
                "messages": messages,
                "query": current_query if current_query else "No query executed",
                "result": query_result if query_result else "No results",
                "error": error if error else "None",
                "role": chat_state.role
            })
            chat_state.add_message(AIMessage(content=response))
            chat_state.response = response
            logger.debug(f"Formatted response: {response}")
            return chat_state.to_dict()
        except Exception as e:
            error_message = f"Sorry, I encountered an error: {str(e)}"
            chat_state.add_message(AIMessage(content=error_message))
            chat_state.error = error_message
            logger.error(error_message)
            return chat_state.to_dict()

    def process_query(self, question: str, email: str) -> str:
        """Process a user query and return a response."""
        if not isinstance(question, str):
            logger.error(f"Invalid question type: {type(question)}")
            raise ValueError("Question must be a string")
        if not isinstance(email, str):
            logger.error(f"Invalid email type: {type(email)}")
            raise ValueError("Email must be a string")
        user_id, role = self._get_user_info(email)
        state = ChatState(
            messages=[HumanMessage(content=question)],
            user_id=user_id,
            role=role,
            email=email
        )
        initial_state = state.to_dict()
        logger.info(f"Initial state messages: {initial_state['messages']}, user_id={user_id}, role={role}")
        try:
            final_state_dict = self.workflow.invoke(initial_state, debug=True)
            if final_state_dict is None:
                logger.error("Workflow returned None state")
                raise ValueError("Workflow failed to return a valid state")
            if not isinstance(final_state_dict, dict):
                logger.error(f"Expected dict from workflow, got {type(final_state_dict)}")
                raise ValueError(f"Expected dict, got {type(final_state_dict)}")
            final_state = ChatState.from_dict(final_state_dict)
            logger.info(f"Final state messages: {[str(m) for m in final_state.messages]}")
            return final_state.response or "Sorry, I couldn't generate a response."
        except Exception as e:
            logger.error(f"Workflow error: {str(e)}")
            raise

    def get_db_schema(self) -> str:
        """Get the database schema."""
        return self.db_schema

    def get_sample_data(self) -> Dict[str, pd.DataFrame]:
        """Get sample data from each table."""
        tables = {}
        for table in self.db.get_usable_table_names():
            query = f"SELECT * FROM {table} LIMIT 5"
            try:
                result = self.sql_tool.invoke({"query": query})
                if isinstance(result, str) and result.startswith('[') and result.endswith(']'):
                    data = json.loads(result)
                    tables[table] = pd.DataFrame(data)
            except Exception as e:
                logger.error(f"Error getting sample data for {table}: {str(e)}")
                continue
        return tables