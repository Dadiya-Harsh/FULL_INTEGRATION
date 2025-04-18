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

    def __init__(self, messages: List[BaseMessage] = None, current_query: str = None, query_result: str = None, error: str = None, response: str = None):
        self.messages = messages or []
        self.current_query = current_query
        self.query_result = query_result
        self.error = error
        self.response = response

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
            response=data.get("response")
        )

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the state."""
        if not isinstance(message, BaseMessage):
            logger.error(f"Invalid message type: {type(message)}")
            raise ValueError(f"Expected BaseMessage, got {type(message)}")
        logger.info(f"Adding message: {message.content} (type: {type(message).__name__})")
        self.messages.append(message)

class SQLChatbot:
    """SQL database chatbot using LangChain and LangGraph."""

    def __init__(self, db_uri: str, openai_api_key: Optional[str] = None):
        """Initialize the SQL chatbot."""
        self.llm = ChatGroq(
            model='llama-3.3-70b-versatile',
            temperature=0,
            api_key=openai_api_key
        )
        self.db = SQLDatabase.from_uri(db_uri)
        self.sql_tool = QuerySQLDataBaseTool(db=self.db)
        self.db_schema = self.db.get_table_info()
        self.workflow = self._build_graph()
        logger.info("SQLChatbot initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(Dict)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("format_response", self._format_response)
        workflow.add_edge("generate_sql", "execute_sql")
        workflow.add_edge("execute_sql", "format_response")
        workflow.add_edge("format_response", END)
        workflow.set_entry_point("generate_sql")
        return workflow.compile()

    def _generate_sql(self, state: Dict) -> Dict:
        """Generate SQL query from natural language question."""
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
            sql_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert SQL query generator.
                Given the database schema and a question, generate a SQL query that answers the question.
                Return only the SQL query as plain text, without any Markdown, code fences (```), or additional formatting.

                Database Schema:
                {schema}"""),
                MessagesPlaceholder(variable_name="messages"),
            ])
            sql_chain = sql_prompt | self.llm | StrOutputParser()
            query = sql_chain.invoke({
                "schema": self.db_schema,
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
            return chat_state.to_dict()
        except Exception as e:
            error_message = f"Error executing SQL query: {str(e)}"
            chat_state.add_message(AIMessage(content=error_message))
            chat_state.error = error_message
            logger.error(error_message)
            return chat_state.to_dict()

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
            Given a user question, SQL query, and query result, provide a clear and helpful response.

            If there was an error, explain it in a friendly manner and suggest a fix if possible.
            If the query was successful, summarize the results and directly answer the user's question."""),
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
                "error": error if error else "None"
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

    def process_query(self, question: str) -> str:
        """Process a user query and return a response."""
        if not isinstance(question, str):
            logger.error(f"Invalid question type: {type(question)}")
            raise ValueError("Question must be a string")
        state = ChatState(messages=[HumanMessage(content=question)])
        initial_state = state.to_dict()
        logger.info(f"Initial state messages: {initial_state['messages']}")
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