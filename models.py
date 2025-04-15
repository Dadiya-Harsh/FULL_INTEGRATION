from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Integer,
    String,
    Float,
    create_engine,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)



class Employee(Base):
    __tablename__ = "employee"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    status = Column(String)
    role = Column(String)


class Meeting(Base):
    __tablename__ = "meeting"
    id = Column(String, primary_key=True, index=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    rolling_sentiments = relationship("RollingSentiment", backref="meeting", cascade="all, delete-orphan")
    employee_skills = relationship("EmployeeSkills", backref="meeting", cascade="all, delete-orphan")
    skill_recommendations = relationship("SkillRecommendation", backref="meeting", cascade="all, delete-orphan")
    task_recommendations = relationship("TaskRecommendation", backref="meeting", cascade="all, delete-orphan")

class RollingSentiment(Base):
    __tablename__ = "rolling_sentiment"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String)
    rolling_sentiment = Column(JSON)

    __table_args__ = (
        UniqueConstraint("meeting_id", "name", name="_unique_meeting_person"),
    )

class EmployeeSkills(Base):
    __tablename__ = "employee_skills"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id"), nullable=False)
    overall_sentiment_score = Column(Float)
    role = Column(String)
    employee_name = Column(String)

class SkillRecommendation(Base):
    __tablename__ = "skill_recommendation"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id"), nullable=False)
    skill_recommendation = Column(String)
    name = Column(String)

class TaskRecommendation(Base):
    __tablename__ = "task_recommendation"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id"), nullable=False)
    task = Column(String)
    assigned_by = Column(String)  # New column
    assigned_to = Column(String)  # New column
    deadline = Column(String)
    status = Column(String)
    # Removed the 'name' column

class MeetingTranscript(Base):
    __tablename__ = "meeting_transcript"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    text = Column(Text)
    processed = Column(Boolean, default=False)
    
    # meeting = relationship("Meeting", backref="transcripts")

# Base.metadata.drop_all(bind = engine)
# Create all tables
Base.metadata.create_all(bind=engine)


# # Optional utility to insert rolling sentiment
def add_rolling_sentiment(session, meeting_id, name, role, rolling_data):
    from sqlalchemy.exc import IntegrityError
    from json import dumps

    sentiment_entry = RollingSentiment(
        meeting_id=meeting_id,
        name=name,
        role=role,
        rolling_sentiment=dumps(rolling_data)
    )

    session.add(sentiment_entry)
    try:
        session.commit()
        print(f"Inserted rolling sentiment for {name}")
    except IntegrityError:
        session.rollback()
        print(f"Rolling sentiment for {name} in meeting {meeting_id} already exists.")
