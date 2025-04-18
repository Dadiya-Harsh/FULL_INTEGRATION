import streamlit as st
import pandas as pd
from modules.db.models import SessionLocal, Employee, Task
import sys
import os
import time
from sql_agent_tool.models import DatabaseConfig, LLMConfig
from sql_agent_tool import SQLAgentTool

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize session state variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'sql_agent' not in st.session_state:
    st.session_state.sql_agent = None
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Function to get database session
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# Initialize SQL Agent Tool
def init_sql_agent():
    # Extract connection information from SessionLocal
    engine = SessionLocal().get_bind()
    url = engine.url
    
    try:
        # Configure database connection for SQLAgentTool
        db_config = DatabaseConfig(
            drivername=url.drivername,
            username=url.username or "",
            password=url.password or "",
            host=url.host or "localhost",
            port=url.port or 5432,
            database=url.database
        )
        
        # Configure LLM for SQLAgentTool
        llm_config = LLMConfig(
            provider="groq",  # Change as needed
            api_key=os.environ.get("GROQ_API_KEY", "your-api-key"),
            model="llama-3.3-70b-versatile",
            max_tokens=500
        )
        
        # Initialize and return the SQL Agent Tool
        agent = SQLAgentTool(db_config, llm_config)
        
        # Log successful initialization
        print("SQL Agent initialized successfully")
        return agent
    except Exception as e:
        print(f"Error initializing SQL Agent: {e}")
        return None

# Database utility functions
def get_employee_by_email(db, email):
    return db.query(Employee).filter(Employee.email == email).first()

def get_employee_tasks(db, employee_id):
    return db.query(Task).filter(Task.assigned_to_id == employee_id).all()

def get_team_tasks(db, manager_id):
    return db.query(Task).join(Employee, Task.assigned_to_id == Employee.id)\
        .filter(Employee.manager_id == manager_id).all()

def get_employee_performance(db, employee_id):
    return {
        "tasks_completed": db.query(Task).filter(
            Task.assigned_to_id == employee_id, 
            Task.status == "completed"
        ).count(),
        "tasks_pending": db.query(Task).filter(
            Task.assigned_to_id == employee_id, 
            Task.status == "pending"
        ).count()
    }

def get_employee_by_name(db, name):
    return db.query(Employee).filter(Employee.name == name).first()

def get_employee_transcripts(db, employee_name):
    # Placeholder - implement based on your actual models
    return []

def create_task(db, title, description, assigned_to_id, created_by_id, deadline=None, priority="medium"):
    task = Task(
        title=title,
        description=description,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        deadline=deadline,
        priority=priority
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

# Simplified authentication with email
def authenticate(email):
    db = get_db()
    employee = get_employee_by_email(db, email)
    if employee:
        st.session_state.authenticated = True
        st.session_state.current_user = employee
        st.session_state.user_role = employee.role
        
        # Initialize SQL Agent Tool on successful authentication
        try:
            st.session_state.sql_agent = init_sql_agent()
            if st.session_state.sql_agent:
                print(f"SQL Agent initialized for user: {employee.name}")
            else:
                print("SQL Agent initialization failed")
        except Exception as e:
            print(f"Error initializing SQL Agent: {e}")
        
        # Initialize welcome message after successful authentication
        st.session_state.messages = [{"role": "assistant", "content": f"Hello {st.session_state.current_user.name}! How can I help you today?"}]
        
        return True
    return False



# Enhanced chatbot functionality with SQL Agent Tool
def chatbot_interface():
    st.title("Work Assistant Chatbot")
    
    # Ensure messages list exists in session state
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": f"Hello {st.session_state.current_user.name}! How can I help you today?"}]
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # User input
    user_input = st.chat_input("Ask me anything...")
    
    if user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Generate response
        with st.spinner("Thinking..."):
            response = enhanced_process_query(user_input)
            
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Display assistant response
        with st.chat_message("assistant"):
            st.write(response)

def enhanced_process_query(query):
    """Process user query with SQL Agent or fallback to rule-based system"""
    print(f"Processing query: {query}")
    
    # Handle greeting separately for quick response
    if any(greeting in query.lower() for greeting in ["hello", "hi", "hey"]) and len(query.split()) < 3:
        return f"Hello {st.session_state.current_user.name}! How can I help you today?"
    
    # Get user info
    role = st.session_state.user_role
    user = st.session_state.current_user
    
    # Check if we can use SQL Agent
    if st.session_state.sql_agent:
        try:
            # Check if query is potentially about database information
            db_keywords = [
                "tasks", "performance", "employees", "team", "completed", 
                "pending", "status", "priority", "deadline", "assigned",
                "who", "what", "how many", "list", "show", "find", "get",
                "employee", "manager", "deadline", "project"
            ]
            
            # Add employee names to keywords for better detection
            db = get_db()
            try:
                employee_names = [emp.name.lower() for emp in db.query(Employee).all()]
                db_keywords.extend(employee_names)
            except:
                pass
                
            # Check if query is DB related
            db_related = any(keyword in query.lower() for keyword in db_keywords)
            
            if db_related:
                print("Query appears to be database-related, using SQL Agent")
                
                # Format query to include context about the user role and ID
                contextualized_query = f"{query} (context: user is {user.name}, role is {role}, user_id is {user.id})"
                
                start_time = time.time()
                result = st.session_state.sql_agent.process_natural_language_query(contextualized_query)
                query_time = time.time() - start_time
                
                print(f"SQL Agent result: success={result.success}, rows={result.row_count if hasattr(result, 'row_count') else 'N/A'}")
                
                if result.success and hasattr(result, 'data') and result.data:
                    # Format the data as a readable response
                    if result.row_count > 0:
                        # Convert to pandas DataFrame for better formatting
                        df = pd.DataFrame(result.data)
                        
                        # Format response based on number of rows
                        if result.row_count <= 5:
                            # For small results, convert to a natural language response
                            response = f"Here's what I found:\n\n"
                            for i, row in df.iterrows():
                                response += ", ".join([f"{col}: {val}" for col, val in row.items() if val is not None]) + "\n"
                        else:
                            # For larger results, show a summary
                            response = f"I found {result.row_count} results. Here's a summary:\n\n"
                            response += df.head(5).to_markdown()
                            response += "\n\n(showing first 5 results)"
                        
                        return response
                    else:
                        print("SQL Agent returned success but no data, falling back")
                        return fallback_process_query(query)
                else:
                    print("SQL Agent query unsuccessful, falling back")
                    return fallback_process_query(query)
            else:
                print("Query doesn't appear database-related, using fallback")
                return fallback_process_query(query)
                
        except Exception as e:
            print(f"Error with SQL Agent: {e}")
            return fallback_process_query(query)
    else:
        print("SQL Agent not available, using fallback")
        return fallback_process_query(query)

# Original rule-based query processor as fallback
def fallback_process_query(query):
    """Process query using rule-based approach"""
    print("Using fallback query processor")
    db = get_db()
    role = st.session_state.user_role
    user = st.session_state.current_user
    
    # Common queries for all roles
    if any(greeting in query.lower() for greeting in ["hello", "hi", "hey"]) and len(query.split()) < 3:
        return f"Hello {user.name}! How can I help you today?"
    
    # Look for employee names in the query
    employee_mentioned = None
    try:
        for emp in db.query(Employee).all():
            if emp.name.lower() in query.lower():
                employee_mentioned = emp
                break
    except:
        pass
    
    # Process based on role
    if role == "Employee":
        if "my tasks" in query.lower() or "what tasks" in query.lower():
            tasks = get_employee_tasks(db, user.id)
            if tasks:
                tasks_text = "\n".join([f"- {task.title} (Priority: {task.priority}, Status: {task.status})" for task in tasks])
                return f"Here are your tasks:\n{tasks_text}"
            else:
                return "You have no assigned tasks at the moment."
                
        if "my performance" in query.lower():
            perf = get_employee_performance(db, user.id)
            return f"You have completed {perf['tasks_completed']} tasks and have {perf['tasks_pending']} pending tasks."
            
        if "my transcript" in query.lower():
            return "You can view your transcripts in the 'My Transcripts' tab."
    
    # Manager queries
    elif role == "manager":
        if "team tasks" in query.lower():
            tasks = get_team_tasks(db, user.id)
            if tasks:
                tasks_text = "\n".join([f"- {task.title} assigned to {task.assignee.name if hasattr(task, 'assignee') else 'Unknown'} (Status: {task.status})" for task in tasks])
                return f"Here are your team's tasks:\n{tasks_text}"
            else:
                return "Your team has no assigned tasks at the moment."
                
        if "assign task" in query.lower():
            return "You can assign tasks to your team members in the 'Assign Task' tab."
            
        if "team performance" in query.lower():
            return "You can view your team's performance in the 'Team Performance' tab."
        
        # If asking about a team member
        if employee_mentioned:
            # Check if this employee is in their team
            if employee_mentioned.manager_id == user.id:
                if "tasks" in query.lower():
                    tasks = get_employee_tasks(db, employee_mentioned.id)
                    if tasks:
                        tasks_text = "\n".join([f"- {task.title} (Status: {task.status})" for task in tasks])
                        return f"{employee_mentioned.name}'s tasks:\n{tasks_text}"
                    else:
                        return f"{employee_mentioned.name} has no assigned tasks at the moment."
                
                if "performance" in query.lower():
                    perf = get_employee_performance(db, employee_mentioned.id)
                    return f"{employee_mentioned.name} has completed {perf['tasks_completed']} tasks and has {perf['tasks_pending']} pending tasks."
                
                # General info about employee
                return f"{employee_mentioned.name} is a {employee_mentioned.role} in your team. You can check their tasks and performance in the Team tabs."
            else:
                return f"{employee_mentioned.name} is not in your team."
    
    # HR queries
    elif role == "hr":
        if "all employees" in query.lower():
            return "You can view all employees in the 'All Employees' tab."
            
        # If asking about a specific employee
        if employee_mentioned:
            if "performance" in query.lower():
                perf = get_employee_performance(db, employee_mentioned.id)
                return f"{employee_mentioned.name} has completed {perf['tasks_completed']} tasks and has {perf['tasks_pending']} pending tasks."
                
            if "tasks" in query.lower():
                tasks = get_employee_tasks(db, employee_mentioned.id)
                if tasks:
                    tasks_text = "\n".join([f"- {task.title} (Status: {task.status})" for task in tasks])
                    return f"{employee_mentioned.name}'s tasks:\n{tasks_text}"
                else:
                    return f"{employee_mentioned.name} has no assigned tasks at the moment."
            
            # General info about employee
            manager = db.query(Employee).filter(Employee.id == employee_mentioned.manager_id).first()
            manager_name = manager.name if manager else "No manager"
            
            return (f"{employee_mentioned.name} is a {employee_mentioned.role} with status '{employee_mentioned.status}'. "
                   f"Their manager is {manager_name}. "
                   f"You can view more details in the Employee Details tab.")
    
    # Information about an employee that anyone can access
    if employee_mentioned:
        if role == "employee" and employee_mentioned.id != user.id:
            return f"{employee_mentioned.name} is a {employee_mentioned.role} in the company. For more details, please contact HR."
    
    # Handle query about tasks
    if "tasks" in query.lower():
        return "You can view task information in the Dashboard tab."
    
    # Query about the system itself
    if any(word in query.lower() for word in ["help", "instructions", "how to use", "guide"]):
        return ("I can help you navigate the Work Assistant system. You can ask me about:\n"
               "- Your tasks and performance\n"
               "- Team information (for managers)\n"
               "- Employee details (for HR)\n"
               "You can also use the Dashboard tab to access all features directly.")
    
    # Default response
    return ("I'm not sure how to help with that specific query. Could you please rephrase or ask about tasks, "
           "performance, or specific employees?")

