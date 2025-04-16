from sqlalchemy.orm import Session
from models import Employee, Task, Meeting, MeetingTranscript, TaskRecommendation
from datetime import datetime

def get_employee_by_id(db: Session, employee_id: int):
    return db.query(Employee).filter(Employee.id == employee_id).first()

def get_employee_by_email(db: Session, email: str):
    return db.query(Employee).filter(Employee.email == email).first()

def get_employee_by_name(db: Session, name: str):
    return db.query(Employee).filter(Employee.name == name).first()

def get_employee_tasks(db: Session, employee_id: int):
    return db.query(Task).filter(Task.assigned_to_id == employee_id).all()

def get_team_tasks(db: Session, manager_id: int):
    return db.query(Task).join(Employee, Task.assigned_to_id == Employee.id)\
        .filter(Employee.manager_id == manager_id).all()

def create_task(db: Session, title: str, description: str, assigned_to_id: int, 
                created_by_id: int, deadline=None, priority="medium"):
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

def get_employee_performance(db: Session, employee_id: int):
    # This is a placeholder - implement based on your requirements
    # Could use RollingSentiment, EmployeeSkills, etc.
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

def get_employee_transcripts(db: Session, employee_name: str):
    return db.query(MeetingTranscript).filter(MeetingTranscript.name == employee_name).all()

def get_task_recommendations(db: Session, employee_name: str):
    return db.query(TaskRecommendation).filter(TaskRecommendation.assigned_to == employee_name).all()