from sqlalchemy import create_engine
from models import Base, Employee, Meeting, MeetingTranscript, RollingSentiment, EmployeeSkills, SkillRecommendation, TaskRecommendation
import os
from dotenv import load_dotenv

load_dotenv()

# Use employee user for initial verification
DATABASE_URL = f"postgresql://{os.getenv('EMPLOYEE_DB_USER')}:{os.getenv('EMPLOYEE_DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)

# Verify tables
Base.metadata.create_all(engine)

# Insert sample data (if not already present)
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(bind=engine)
with SessionLocal() as session:
    # Check if employees exist
    if not session.query(Employee).filter_by(email='john.doe@example.com').first():
        session.add_all([
            Employee(name='John Doe', email='john.doe@example.com', role='employee', status='active', phone='123-456-7890'),
            Employee(name='Jane Manager', email='jane.manager@example.com', role='manager', status='active', phone='123-456-7891'),
            Employee(name='HR User', email='hr.user@example.com', role='hr', status='active', phone='123-456-7892')
        ])
    
    # Check if meeting exists
    if not session.query(Meeting).filter_by(id='meeting1').first():
        session.add(Meeting(id='meeting1', title='Team Sync'))
    
    # Check if transcript exists
    if not session.query(MeetingTranscript).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(MeetingTranscript(meeting_id='meeting1', name='John Doe', text='Discussed project updates.', processed=True))
    
    # Check if sentiment exists
    if not session.query(RollingSentiment).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(RollingSentiment(meeting_id='meeting1', name='John blancosDoe', role='employee', rolling_sentiment={'positive': 0.8, 'negative': 0.1, 'neutral': 0.1}))
    
    # Check if skills exist
    if not session.query(EmployeeSkills).filter_by(meeting_id='meeting1', employee_name='John Doe').first():
        session.add(EmployeeSkills(meeting_id='meeting1', overall_sentiment_score=0.85, role='employee', employee_name='John Doe'))
    
    # Check if skill recommendation exists
    if not session.query(SkillRecommendation).filter_by(meeting_id='meeting1', name='John Doe').first():
        session.add(SkillRecommendation(meeting_id='meeting1', skill_recommendation='Improve communication skills', name='John Doe'))
    
    # Check if task recommendation exists
    if not session.query(TaskRecommendation).filter_by(meeting_id='meeting1', assigned_to='John Doe').first():
        session.add(TaskRecommendation(meeting_id='meeting1', task='Prepare presentation', assigned_by='Jane Manager', assigned_to='John Doe', deadline='2025-04-30', status='pending'))
    
    session.commit()