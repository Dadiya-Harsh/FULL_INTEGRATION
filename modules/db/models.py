#=====================================
# Database Setup and Models 
#=====================================

from sqlalchemy import (
    JSON, Boolean, Column, Integer, String, Float, create_engine,
    ForeignKey, DateTime, UniqueConstraint, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Base = declarative_base()

# Setup DB connection
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


#=====================================
# Meeting Table
#=====================================

class Meeting(Base):
    __tablename__ = "meeting"

    id = Column(String, primary_key=True, index=True)  # UUID as string
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships to linked tables
    transcripts = relationship("MeetingTranscript", backref="meeting", cascade="all, delete-orphan")
    rolling_sentiments = relationship("RollingSentiment", backref="meeting", cascade="all, delete-orphan")
    employee_skills = relationship("EmployeeSkills", backref="meeting", cascade="all, delete-orphan")
    skill_recommendations = relationship("SkillRecommendation", backref="meeting", cascade="all, delete-orphan")
    task_recommendations = relationship("TaskRecommendation", backref="meeting", cascade="all, delete-orphan")

#=====================================
# Employee Table
#=====================================

class Employee(Base):
    __tablename__ = "employee"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    status = Column(String)
    role = Column(String)

#=====================================
# Transcript Table
#=====================================

class MeetingTranscript(Base):
    __tablename__ = "meeting_transcript"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    text = Column(Text)
    processed = Column(Boolean, default=False)

#=====================================
# Rolling Sentiment Table
#=====================================

class RollingSentiment(Base):
    __tablename__ = "rolling_sentiment"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String)
    rolling_sentiment = Column(JSON)

    __table_args__ = (
        UniqueConstraint("meeting_id", "name", name="_unique_meeting_person"),
    )

#=====================================
# Employee Sentiment Summary Table
#=====================================

class EmployeeSkills(Base):
    __tablename__ = "employee_skills"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    overall_sentiment_score = Column(Float)
    role = Column(String)
    employee_name = Column(String)

#=====================================
# Skill Recommendation Table
#=====================================

class SkillRecommendation(Base):
    __tablename__ = "skill_recommendation"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    skill_recommendation = Column(String)
    name = Column(String)


#=====================================
# Task Recommendation Table
#=====================================

class TaskRecommendation(Base):
    __tablename__ = "task_recommendation"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    task = Column(String)
    assigned_by = Column(String)
    assigned_to = Column(String)
    deadline = Column(String)
    status = Column(String)

#=====================================
# Table Creation and Utility Function
#=====================================

# Create all tables in DB
Base.metadata.create_all(bind=engine)

# Utility to safely insert a rolling sentiment entry
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
