#=====================================
# Database Setup and Models 
#=====================================

from sqlalchemy import (
    JSON, Boolean, Column, Integer, String, Float, create_engine,
    ForeignKey, DateTime, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base
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

class Role(Base):
    __tablename__ = "role"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 'employee', 'manager', 'hr'
    description = Column(Text)
    
    # Relationships
    permissions = relationship("RolePermission", back_populates="role")
    users = relationship("UserRole", back_populates="role")


class Permission(Base):
    __tablename__ = "permission"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 'view_tasks', 'assign_tasks', etc.
    description = Column(Text)
    resource_type = Column(String, nullable=False)  # 'tasks', 'transcripts', etc.
    
    # Relationships
    roles = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    __tablename__ = "role_permission"
    role_id = Column(Integer, ForeignKey("role.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permission.id"), primary_key=True)
    
    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")


class Team(Base):
    __tablename__ = "team"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Relationships
    members = relationship("TeamMember", back_populates="team")
    tasks = relationship("Task", back_populates="team")


class Employee(Base):
    __tablename__ = "employee"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    status = Column(String)
    role = Column(String)  # 'employee', 'manager', 'hr'
    # Remove the role column as we'll use the role relationship instead
    manager_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    
    # Existing relationships
    subordinates = relationship("Employee", backref="manager", remote_side=[id])
    assigned_tasks = relationship("Task", backref="assignee", foreign_keys="Task.assigned_to_id")
    created_tasks = relationship("Task", backref="creator", foreign_keys="Task.created_by_id")
    
    # New relationships for RBAC
    roles = relationship("UserRole", back_populates="employee")
    teams = relationship("TeamMember", back_populates="employee")
    access_logs = relationship("AccessLog", back_populates="employee")


class UserRole(Base):
    __tablename__ = "user_role"
    employee_id = Column(Integer, ForeignKey("employee.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("role.id"), primary_key=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="roles")
    role = relationship("Role", back_populates="users")


class TeamMember(Base):
    __tablename__ = "team_member"
    team_id = Column(Integer, ForeignKey("team.id"), primary_key=True)
    employee_id = Column(Integer, ForeignKey("employee.id"), primary_key=True)
    is_manager = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="members")
    employee = relationship("Employee", back_populates="teams")


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
    team_id = Column(Integer, ForeignKey("team.id"), nullable=True)  # Associate tasks with teams
    
    # Added team relationship
    team = relationship("Team", back_populates="tasks")

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
class AccessLog(Base):
    __tablename__ = "access_log"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employee.id"))
    resource_type = Column(String, nullable=False)  # 'tasks', 'transcripts', etc.
    resource_id = Column(Integer)
    action = Column(String, nullable=False)  # 'view', 'create', 'update', 'delete'
    timestamp = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, nullable=False)
    
    # Relationships
    employee = relationship("Employee", back_populates="access_logs")

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

# Helper functions for RBAC checks
def get_user_permissions(session, employee_id):
    """Get all permissions for a user."""
    return session.query(Permission)\
        .join(RolePermission, Permission.id == RolePermission.permission_id)\
        .join(UserRole, RolePermission.role_id == UserRole.role_id)\
        .filter(UserRole.employee_id == employee_id)\
        .all()

def check_user_permission(session, employee_id, permission_name, resource_type=None):
    """Check if a user has a specific permission."""
    query = session.query(Permission)\
        .join(RolePermission, Permission.id == RolePermission.permission_id)\
        .join(UserRole, RolePermission.role_id == UserRole.role_id)\
        .filter(UserRole.employee_id == employee_id)\
        .filter(Permission.name == permission_name)
    
    if resource_type:
        query = query.filter(Permission.resource_type == resource_type)
    
    return query.first() is not None

def is_team_manager(session, employee_id, team_id):
    """Check if an employee is a manager of a specific team."""
    return session.query(TeamMember)\
        .filter(TeamMember.employee_id == employee_id)\
        .filter(TeamMember.team_id == team_id)\
        .filter(TeamMember.is_manager == True)\
        .first() is not None

def get_employee_teams(session, employee_id):
    """Get all teams an employee belongs to."""
    return session.query(Team)\
        .join(TeamMember, Team.id == TeamMember.team_id)\
        .filter(TeamMember.employee_id == employee_id)\
        .all()

def log_access(session, employee_id, resource_type, resource_id, action, success=True):
    """Log an access attempt."""
    log = AccessLog(
        employee_id=employee_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        success=success
    )
    session.add(log)
    session.commit()
    return log

# Base.metadata.drop_all(bind=engine)  # Uncomment to reset tables
Base.metadata.create_all(bind=engine)