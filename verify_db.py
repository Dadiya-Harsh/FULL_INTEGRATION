from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from modules.db.models import Base, Employee, Meeting, MeetingTranscript, RollingSentiment, EmployeeSkills, SkillRecommendation, TaskRecommendation
import os
from dotenv import load_dotenv

load_dotenv()

# Use sudo user for setup
DATABASE_URL = f"postgresql://{os.getenv('SUDO_DB_USER')}:{os.getenv('SUDO_DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(bind=engine)
with SessionLocal() as session:
    # Set app.current_user for RLS
    with engine.connect() as conn:
        conn.execute(text("SET app.current_user = 'john.doe@example.com'"))
        conn.commit()

    # Disable autoflush to avoid premature commits
    session.autoflush = False

    # Insert sample data if not present
    if not session.query(Employee).filter_by(email='john.doe@example.com').first():
        session.add_all([
            Employee(name='John Doe', email='john.doe@example.com', role='employee', status='active', phone='123-456-7890'),
            Employee(name='Jane Manager', email='jane.manager@example.com', role='manager', status='active', phone='123-456-7891'),
            Employee(name='HR User', email='hr.user@example.com', role='hr', status='active', phone='123-456-7892')
        ])
    
    if not session.query(Meeting).filter_by(id='meeting1').first():
        session.add(Meeting(id='meeting1', title='Team Sync'))
    
    if not session.query(MeetingTranscript).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(MeetingTranscript(meeting_id='meeting1', name='John Doe', text='Discussed project updates.', processed=True))
    
    if not session.query(RollingSentiment).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(RollingSentiment(meeting_id='meeting1', name='John Doe', role='employee', rolling_sentiment={'positive': 0.8, 'negative': 0.1, 'neutral': 0.1}))
    
    if not session.query(EmployeeSkills).filter_by(meeting_id='meeting1', employee_name='John Doe').first():
        session.add(EmployeeSkills(meeting_id='meeting1', overall_sentiment_score=0.85, role='employee', employee_name='John Doe'))
    
    if not session.query(SkillRecommendation).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(SkillRecommendation(meeting_id='meeting1', skill_recommendation='Improve communication skills', name='John Doe'))
    
    if not session.query(TaskRecommendation).filter_by(meeting_id='meeting1', assigned_to='John Doe').first():
        session.add(TaskRecommendation(meeting_id='meeting1', task='Prepare presentation', assigned_by='Jane Manager', assigned_to='John Doe', deadline='2025-04-30', status='pending'))
    
    session.commit()