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
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Meeting(Base):
    __tablename__ = "meeting"
    id = Column(String, primary_key=True, index=True)  # UUID as String
    title = Column(String)  # Optional fields
    created_at = Column(DateTime, default=datetime.utcnow)

    transcripts = relationship("MeetingTranscript", backref="meeting", cascade="all, delete-orphan")
    rolling_sentiments = relationship("RollingSentiment", backref="meeting", cascade="all, delete-orphan")
    employee_skills = relationship("EmployeeSkills", backref="meeting", cascade="all, delete-orphan")
    skill_recommendations = relationship("SkillRecommendation", backref="meeting", cascade="all, delete-orphan")
    task_recommendations = relationship("TaskRecommendation", backref="meeting", cascade="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employee"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    status = Column(String)
    role = Column(String)  # 'employee', 'manager', or 'hr'
    manager_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    
    # Relationships
    subordinates = relationship("Employee", backref="manager", remote_side=[id])
    assigned_tasks = relationship("Task", backref="assignee", foreign_keys="Task.assigned_to_id")
    created_tasks = relationship("Task", backref="creator", foreign_keys="Task.created_by_id")


class Task(Base):
    __tablename__ = "task"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")  # pending, in_progress, completed
    priority = Column(String, default="medium")  # low, medium, high
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    
    # Foreign keys
    assigned_to_id = Column(Integer, ForeignKey("employee.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("employee.id"), nullable=False)


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcript"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # meeting_id = Column(String, nullable=False)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)
    text = Column(Text)
    processed = Column(Boolean, default=False)


class RollingSentiment(Base):
    __tablename__ = "rolling_sentiment"
    id = Column(Integer, primary_key=True, index=True)
    # meeting_id = Column(String, ForeignKey("meeting_transcript.id", ondelete="CASCADE"), nullable=False)
    
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)
    role = Column(String)
    rolling_sentiment = Column(JSON)

    __table_args__ = (
        UniqueConstraint("meeting_id", "name", name="_unique_meeting_person"),
    )


class EmployeeSkills(Base):
    __tablename__ = "employee_skills"
    id = Column(Integer, primary_key=True, index=True)
    # meeting_id = Column(String, ForeignKey("meeting_transcript.id", ondelete="CASCADE"), nullable=False)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)

    overall_sentiment_score = Column(Float)
    role = Column(String)
    employee_name = Column(String)


class SkillRecommendation(Base):
    __tablename__ = "skill_recommendation"
    id = Column(Integer, primary_key=True, index=True)
    # meeting_id = Column(String, ForeignKey("meeting_transcript.id", ondelete="CASCADE"), nullable=False)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)

    skill_recommendation = Column(String)
    name = Column(String)


class TaskRecommendation(Base):
    __tablename__ = "task_recommendation"
    id = Column(Integer, primary_key=True, index=True)
    # meeting_id = Column(String, ForeignKey("meeting_transcript.id", ondelete="CASCADE"), nullable=False)
    meeting_id = Column(String, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)

    task = Column(String)
    assigned_by = Column(String)
    assigned_to = Column(String)
    deadline = Column(String)
    status = Column(String)


# Base.metadata.drop_all(bind=engine)  # Uncomment to reset tables
# Base.metadata.create_all(bind=engine)