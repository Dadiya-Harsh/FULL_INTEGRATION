# chatbot/app/langgraph_workflow.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.messages import HumanMessage, AIMessage
import os
from dotenv import load_dotenv

load_dotenv()

# Define the state structure
class GraphState:
    def __init__(self):
        self.messages = []
        self.employee_id = None
        self.db = None
        self.response = {}

# Nodes in the workflow
def intent_recognition(state):
    messages = state.messages
    last_message = messages[-1].content if messages else ""
    
    # Simple intent detection
    if any(keyword in last_message.lower() for keyword in ["task", "employee", "team", "role"]):
        return "rbac_query"
    return "general_query"

def rbac_query(state):
    db = SQLDatabase.from_uri(state.db)
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    # Use the query tool (first tool in the toolkit, typically for running SQL queries)
    query_tool = tools[0]  # Adjust index based on your toolkit structure
    
    # Construct a query with RBAC filter (example, adjust based on your schema)
    query = f"SELECT * FROM tasks WHERE employee_id = {state.employee_id}"
    if "employee" in state.messages[-1].content.lower():
        query = f"SELECT * FROM employees WHERE id = {state.employee_id}"
    
    result = query_tool.run({"query": state.messages[-1].content})
    state.response = {
        "status": "success",
        "message": f"Found results for your query",
        "data": {"result": result}
    }
    return "aggregate_response"

def general_query(state):
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    response = llm.invoke(state.messages)
    state.response = {
        "status": "success",
        "message": response.content,
        "data": {}
    }
    return "aggregate_response"

def aggregate_response(state):
    state.messages.append(AIMessage(content=state.response))
    return END

# Build the graph
def initialize_workflow(employee_id, db_uri):
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("intent_recognition", intent_recognition)
    workflow.add_node("rbac_query", rbac_query)
    workflow.add_node("general_query", general_query)
    workflow.add_node("aggregate_response", aggregate_response)
    
    # Define edges
    workflow.set_entry_point("intent_recognition")
    workflow.add_edge("intent_recognition", "rbac_query")
    workflow.add_edge("intent_recognition", "general_query")
    workflow.add_edge("rbac_query", "aggregate_response")
    workflow.add_edge("general_query", "aggregate_response")
    
    # Use MemorySaver instead of SqliteSaver
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    # Initialize state with employee_id and database
    initial_state = GraphState()
    initial_state.employee_id = employee_id
    initial_state.db = db_uri
    return app