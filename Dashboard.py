
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.db.models import Base, Employee, EmployeeSkills, SkillRecommendation, TaskRecommendation, RollingSentiment
import pandas as pd
import json
import os

from dotenv import load_dotenv
load_dotenv()
# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize session state
for key in ['authenticated', 'user_role', 'user_name', 'user_email']:
    if key not in st.session_state:
        st.session_state[key] = False if key == 'authenticated' else None

st.set_page_config(page_title="Employee Dashboard", layout="wide")

# -------------------- Helper Functions --------------------

def get_employee_by_email(email):
    with SessionLocal() as db:
        return db.query(Employee).filter(Employee.email == email).first()


def get_skills_for_employee(name, meeting_id=None):
    with SessionLocal() as db:
        query = db.query(
            SkillRecommendation.skill_recommendation,
            Meeting.created_at
        ).join(Meeting, SkillRecommendation.meeting_id == Meeting.id).filter(
            SkillRecommendation.name == name
        )
        if meeting_id:
            if isinstance(meeting_id, list):
                query = query.filter(SkillRecommendation.meeting_id.in_(meeting_id))
            else:
                query = query.filter(SkillRecommendation.meeting_id == meeting_id)

        return [
            {
                "skill": s.skill_recommendation,
                "meeting_date": s.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for s in query.all()
        ]


def get_tasks_for_employee(name, meeting_ids=None):
    with SessionLocal() as db:
        query = db.query(TaskRecommendation).filter(
            (TaskRecommendation.assigned_to == name) | 
            (TaskRecommendation.assigned_by == name)
        )
        if meeting_ids:
            if isinstance(meeting_ids, list):
                query = query.filter(TaskRecommendation.meeting_id.in_(meeting_ids))
            else:
                query = query.filter(TaskRecommendation.meeting_id == meeting_ids)
        return query.all()


def get_sentiment_data(name, meeting_ids=None):
    with SessionLocal() as db:
        query = db.query(EmployeeSkills).filter(
            EmployeeSkills.employee_name == name
        )
        if meeting_ids:
            if isinstance(meeting_ids, list):
                query = query.filter(EmployeeSkills.meeting_id.in_(meeting_ids))
            else:
                query = query.filter(EmployeeSkills.meeting_id == meeting_ids)
        return query.all()


def get_rolling_sentiment(name, meeting_id=None):
    with SessionLocal() as db:
        query = db.query(RollingSentiment).filter(RollingSentiment.name == name)
        if meeting_id:
            query = query.filter(RollingSentiment.meeting_id == meeting_id)
        rolling = query.first()
        return json.loads(rolling.rolling_sentiment) if rolling else None

def get_all_employees(role_filter=None):
    with SessionLocal() as db:
        query = db.query(Employee)
        if role_filter:
            query = query.filter(Employee.role == role_filter)
        return query.all()

from modules.db.models import Meeting, EmployeeSkills

def get_employee_meetings(name):
    with SessionLocal() as db:
        meetings = db.query(
            Meeting.id, Meeting.created_at
        ).join(EmployeeSkills, Meeting.id == EmployeeSkills.meeting_id).filter(
            EmployeeSkills.employee_name == name
        ).distinct().order_by(Meeting.created_at.desc()).all()
        
        return [{"id": m[0], "created_at": m[1]} for m in meetings]

# -------------------- UI Pages --------------------

def login_page():
    st.markdown("<h1 style='text-align:center;'>🔐 Employee Dashboard Login</h1>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=True):
        st.text_input("📧 Enter your email", key="login_email")
        if st.form_submit_button("Login"):
            emp = get_employee_by_email(st.session_state.login_email)
            if emp:
                st.session_state.authenticated = True
                st.session_state.user_role = emp.role
                st.session_state.user_name = emp.name
                st.session_state.user_email = emp.email
                st.rerun()
            else:
                st.error("🚫 Invalid email or employee not found")
def display_meeting_data(name, meeting_id=None):
    meetings = get_employee_meetings(name)
    if not meetings:
        st.warning("No meeting data available for this employee.")
        return

    st.markdown("### 📅 Select Meeting(s)")
    selected = st.multiselect(
        "Meeting List",
        options=meetings,
        format_func=lambda m: m["created_at"].strftime("🗓 %Y-%m-%d %H:%M"),
        default=[meetings[0]],
        key=f"meeting_multiselect_{name}"
    )

    selected_meeting_ids = [m["id"] for m in selected]

    if not selected_meeting_ids:
        st.info("Please select at least one meeting to display data.")
        return

    

    col1, col2 = st.columns(2)

    with col1:
        with st.expander("📚 Skill Recommendations", expanded=True):
            skills = get_skills_for_employee(name, selected_meeting_ids)
            if skills:
                for skill in skills:
                    st.success(f"✅ {skill['skill']} (Meeting {skill['meeting_date']})")
            else:
                st.info("No skill recommendations for the selected meeting(s).")

    with col2:
        with st.expander("🛠️ Task Recommendations", expanded=True):
            tasks = get_tasks_for_employee(name, selected_meeting_ids)
            if tasks:
                for task in tasks:
                    status = "✅" if task.status.lower() == "completed" else "⏳"
                    st.markdown(f"**{status} {task.task}**  \nAssigned by: `{task.assigned_by}` | Deadline: `{task.deadline}`")
            else:
                st.info("No tasks found for the selected meeting(s).")

    st.markdown("### 📊 Sentiment Analysis")
    sentiments = get_sentiment_data(name, selected_meeting_ids)
    if sentiments:
        avg_sentiment = sum(s.overall_sentiment_score for s in sentiments) / len(sentiments)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("Average Sentiment", f"{avg_sentiment:.2f}")
        with col2:
            rolling_scores = []
            for meeting_id in selected_meeting_ids:
                rolling = get_rolling_sentiment(name, meeting_id)
                if rolling:
                    rolling_scores.extend(rolling["scores"])
            if rolling_scores:
                df = pd.DataFrame(rolling_scores).set_index('Index')
                st.line_chart(df)
            else:
                st.info("No rolling sentiment data found.")
    else:
        st.warning("No sentiment data found for the selected meeting(s).")


def employee_dashboard():
    st.markdown(f"## 👋 Welcome, **{st.session_state.user_name}** ({st.session_state.user_role})")
    st.divider()
    display_meeting_data(st.session_state.user_name)
    
def manager_dashboard():
    st.markdown(f"## 👋 Welcome, **{st.session_state.user_name}** ({st.session_state.user_role})")
    st.divider()

    # ✅ Removed outer expander to avoid nesting
    st.markdown("### 📈 Your Data")
    display_meeting_data(st.session_state.user_name)

    st.markdown("### 👥 Team Overview")
    employee_names = [e.name for e in get_all_employees(role_filter="Employee")]
    selected = st.selectbox(
        "🔍 Select an employee", 
        employee_names, 
        key=f"employee_selectbox_manager_{st.session_state.user_name}"  # Unique key for each manager
    )
    if selected:
        display_meeting_data(selected)

def hr_dashboard():
    st.markdown(f"## 👋 Welcome, **{st.session_state.user_name}** ({st.session_state.user_role})")
    st.divider()

    # ✅ Removed outer expander to avoid nesting
    st.markdown("### 📈 Your Data")
    display_meeting_data(st.session_state.user_name)

    st.markdown("### 🧑‍💼 View Employee/Manager Data")
    all_emps = get_all_employees()
    names = [emp.name for emp in all_emps if emp.role != 'HR']
    selected = st.selectbox(
        "🔍 Select a member", 
        names,
        key=f"employee_selectbox_hr_{st.session_state.user_name}"  # Unique key for HR
    )
    if selected:
        display_meeting_data(selected)

    st.markdown("### 🌐 Organization Overview")
    total_emps = sum(1 for e in all_emps if e.role == 'Employee')
    total_mgrs = sum(1 for e in all_emps if e.role == 'Manager')
    total_hr = sum(1 for e in all_emps if e.role == 'HR')

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👨‍💼 Employees", total_emps)
    col2.metric("👩‍💼 Managers", total_mgrs)
    col3.metric("🧑‍💼 HRs", total_hr)
    col4.metric("🌐 Total Users", len(all_emps))


# -------------------- Main App --------------------

def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=80)
            st.markdown(f"### 👤 {st.session_state.user_name}")
            st.caption(f"📧 {st.session_state.user_email}")
            st.caption(f"🧾 Role: `{st.session_state.user_role}`")
            st.markdown("---")
            if st.button("🚪 Logout"):
                for key in ['authenticated', 'user_role', 'user_name', 'user_email']:
                    st.session_state[key] = False if key == 'authenticated' else None
                st.rerun()

        if st.session_state.user_role == "HR":
            hr_dashboard()
        elif st.session_state.user_role == "Manager":
            manager_dashboard()
        else:
            employee_dashboard()

if __name__ == "__main__":
    main()
