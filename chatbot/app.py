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

# Sidebar for authentication
def login_sidebar():
    st.sidebar.title("Login")
    email = st.sidebar.text_input("Email")
    if st.sidebar.button("Login"):
        if authenticate(email):
            st.sidebar.success(f"Logged in as {st.session_state.current_user.name}")
        else:
            st.sidebar.error("Invalid email")

# Role-based content
def show_employee_view():
    st.title(f"Welcome, {st.session_state.current_user.name}")
    
    # Navigation
    tab1, tab2, tab3 = st.tabs(["My Tasks", "My Performance", "My Transcripts"])
    
    with tab1:
        st.header("My Tasks")
        db = get_db()
        tasks = get_employee_tasks(db, st.session_state.current_user.id)
        if tasks:
            task_data = [{
                "ID": task.id,
                "Title": task.title,
                "Description": task.description,
                "Status": task.status,
                "Priority": task.priority,
                "Deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else "No deadline"
            } for task in tasks]
            st.table(pd.DataFrame(task_data))
        else:
            st.info("No tasks assigned to you.")
    
    with tab2:
        st.header("My Performance")
        db = get_db()
        performance = get_employee_performance(db, st.session_state.current_user.id)
        st.metric("Tasks Completed", performance["tasks_completed"])
        st.metric("Tasks Pending", performance["tasks_pending"])
    
    with tab3:
        st.header("My Transcripts")
        db = get_db()
        transcripts = get_employee_transcripts(db, st.session_state.current_user.name)
        if transcripts:
            for transcript in transcripts:
                with st.expander(f"Meeting: {transcript.meeting.title if hasattr(transcript, 'meeting') and transcript.meeting else 'Unknown'}"):
                    st.write(transcript.text)
        else:
            st.info("No transcripts available.")

def show_manager_view():
    st.title(f"Manager Dashboard - {st.session_state.current_user.name}")
    
    # Navigation
    tab1, tab2, tab3, tab4 = st.tabs(["Team Tasks", "Assign Task", "Team Performance", "Team Transcripts"])
    
    with tab1:
        st.header("Team Tasks")
        db = get_db()
        tasks = get_team_tasks(db, st.session_state.current_user.id)
        if tasks:
            task_data = [{
                "ID": task.id,
                "Assignee": task.assignee.name if hasattr(task, 'assignee') else "Unknown",
                "Title": task.title,
                "Status": task.status,
                "Priority": task.priority,
                "Deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else "No deadline"
            } for task in tasks]
            st.table(pd.DataFrame(task_data))
        else:
            st.info("No tasks assigned to your team.")
    
    with tab2:
        st.header("Assign New Task")
        db = get_db()
        team_members = db.query(Employee).filter(Employee.manager_id == st.session_state.current_user.id).all()
        
        if team_members:
            team_options = {member.name: member.id for member in team_members}
            selected_member = st.selectbox("Select Team Member", list(team_options.keys()))
            
            task_title = st.text_input("Task Title")
            task_desc = st.text_area("Task Description")
            task_priority = st.selectbox("Priority", ["low", "medium", "high"])
            task_deadline = st.date_input("Deadline")
            
            if st.button("Assign Task"):
                if task_title and selected_member:
                    create_task(
                        db, 
                        title=task_title,
                        description=task_desc,
                        assigned_to_id=team_options[selected_member],
                        created_by_id=st.session_state.current_user.id,
                        deadline=task_deadline,
                        priority=task_priority
                    )
                    st.success(f"Task assigned to {selected_member}")
                else:
                    st.error("Please fill in all required fields")
        else:
            st.info("You don't have any team members to assign tasks to.")
    
    with tab3:
        st.header("Team Performance")
        db = get_db()
        team_members = db.query(Employee).filter(Employee.manager_id == st.session_state.current_user.id).all()
        
        if team_members:
            performance_data = []
            for member in team_members:
                perf = get_employee_performance(db, member.id)
                performance_data.append({
                    "Name": member.name,
                    "Tasks Completed": perf["tasks_completed"],
                    "Tasks Pending": perf["tasks_pending"],
                    "Completion Rate": f"{perf['tasks_completed'] / (perf['tasks_completed'] + perf['tasks_pending']) * 100:.1f}%" if (perf['tasks_completed'] + perf['tasks_pending']) > 0 else "N/A"
                })
            st.table(pd.DataFrame(performance_data))
        else:
            st.info("You don't have any team members.")
    
    with tab4:
        st.header("Team Transcripts")
        db = get_db()
        team_members = db.query(Employee).filter(Employee.manager_id == st.session_state.current_user.id).all()
        
        if team_members:
            member_names = [member.name for member in team_members]
            selected_member = st.selectbox("Select Team Member", member_names)
            
            transcripts = get_employee_transcripts(db, selected_member)
            if transcripts:
                for transcript in transcripts:
                    with st.expander(f"Meeting: {transcript.meeting.title if hasattr(transcript, 'meeting') and transcript.meeting else 'Unknown'}"):
                        st.write(transcript.text)
            else:
                st.info(f"No transcripts available for {selected_member}.")
        else:
            st.info("You don't have any team members.")

def show_hr_view():
    st.title(f"HR Dashboard - {st.session_state.current_user.name}")
    
    # Navigation
    tab1, tab2 = st.tabs(["All Employees", "Employee Details"])
    
    with tab1:
        st.header("All Employees")
        db = get_db()
        employees = db.query(Employee).all()
        
        if employees:
            employee_data = [{
                "ID": emp.id,
                "Name": emp.name,
                "Email": emp.email,
                "Role": emp.role,
                "Status": emp.status
            } for emp in employees]
            st.table(pd.DataFrame(employee_data))
        else:
            st.info("No employees found.")
    
    with tab2:
        st.header("Employee Details")
        db = get_db()
        employees = db.query(Employee).all()
        
        if employees:
            employee_names = [emp.name for emp in employees]
            selected_employee = st.selectbox("Select Employee", employee_names)
            employee = get_employee_by_name(db, selected_employee)
            
            if employee:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Personal Information")
                    st.write(f"**ID:** {employee.id}")
                    st.write(f"**Name:** {employee.name}")
                    st.write(f"**Email:** {employee.email}")
                    st.write(f"**Phone:** {employee.phone}")
                    st.write(f"**Role:** {employee.role}")
                    st.write(f"**Status:** {employee.status}")
                
                with col2:
                    st.subheader("Performance")
                    performance = get_employee_performance(db, employee.id)
                    st.metric("Tasks Completed", performance["tasks_completed"])
                    st.metric("Tasks Pending", performance["tasks_pending"])
                
                st.subheader("Tasks")
                tasks = get_employee_tasks(db, employee.id)
                if tasks:
                    task_data = [{
                        "ID": task.id,
                        "Title": task.title,
                        "Status": task.status,
                        "Priority": task.priority,
                        "Deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else "No deadline"
                    } for task in tasks]
                    st.table(pd.DataFrame(task_data))
                else:
                    st.info("No tasks assigned to this employee.")
                
                st.subheader("Transcripts")
                transcripts = get_employee_transcripts(db, employee.name)
                if transcripts:
                    for transcript in transcripts:
                        with st.expander(f"Meeting: {transcript.meeting.title if hasattr(transcript, 'meeting') and transcript.meeting else 'Unknown'}"):
                            st.write(transcript.text)
                else:
                    st.info("No transcripts available for this employee.")
            else:
                st.error("Employee not found.")
        else:
            st.info("No employees found.")

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
    if role == "employee":
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

# Main app
def main():
    st.set_page_config(page_title="Work Assistant", layout="wide")
    
    # Show login if not authenticated
    if not st.session_state.authenticated:
        login_sidebar()
        st.title("Work Assistant")
        st.write("Please login to access the system.")
    else:
        # Logout button
        if st.sidebar.button("Logout"):
            # Clean up SQL Agent if it exists
            if st.session_state.sql_agent:
                try:
                    st.session_state.sql_agent.close()
                except:
                    pass
                
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.session_state.user_role = None
            st.session_state.sql_agent = None
            st.session_state.messages = []
            st.rerun()
        
        # Show appropriate view based on role
        tab1, tab2 = st.tabs(["Dashboard", "Chatbot"])
        
        with tab1:
            if st.session_state.user_role == "employee":
                show_employee_view()
            elif st.session_state.user_role == "manager":
                show_manager_view()
            elif st.session_state.user_role == "hr":
                show_hr_view()
            else:
                st.error("Unknown role. Please contact administrator.")
        
        with tab2:
            chatbot_interface()

if __name__ == "__main__":
    main()