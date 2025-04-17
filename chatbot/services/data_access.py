# -*- coding: utf-8 -*-
# services/data_access.py
import logging
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Union
from modules.db.models import (
    Employee, Task, Meeting, MeetingTranscript, RollingSentiment,
    EmployeeSkills, SkillRecommendation, TaskRecommendation, AccessLog
)
from chatbot.services.rbac_service import RBACService
from datetime import datetime

class DataAccessLayer:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.rbac = RBACService(db_session)
    
    # ====== Employee Access Methods ======
    
    def get_employee(self, employee_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get employee details with RBAC checks."""
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        
        if not employee:
            return {"data": None, "error": "Employee not found"}
        
        # Self-access is always allowed
        if employee_id == current_user_id:
            self.rbac.log_access(current_user_id, "employee", employee_id, "view", True)
            return {"data": self._serialize_employee(employee), "error": None}
        
        # Manager can view their subordinates
        if employee.manager_id == current_user_id:
            self.rbac.log_access(current_user_id, "employee", employee_id, "view", True)
            return {"data": self._serialize_employee(employee), "error": None}
        
        # HR can view all employees
        if self.rbac.has_role(current_user_id, "hr") and \
           self.rbac.has_permission(current_user_id, "view_all_employees"):
            self.rbac.log_access(current_user_id, "employee", employee_id, "view", True)
            return {"data": self._serialize_employee(employee), "error": None}
        
        # Access denied
        self.rbac.log_access(current_user_id, "employee", employee_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    def get_employees(self, current_user_id: int) -> Dict[str, Any]:
        """Get employees with RBAC filtering."""
        # HR can view all employees
        if self.rbac.has_role(current_user_id, "hr") and \
           self.rbac.has_permission(current_user_id, "view_all_employees"):
            employees = self.db.query(Employee).all()
            self.rbac.log_access(current_user_id, "employees", 0, "view_all", True)
            return {"data": [self._serialize_employee(emp) for emp in employees], "error": None}
        
        # Manager can view themselves and their subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            employees = self.db.query(Employee).filter(
                (Employee.id == current_user_id) | 
                (Employee.manager_id == current_user_id)
            ).all()
            self.rbac.log_access(current_user_id, "employees", 0, "view_team", True)
            return {"data": [self._serialize_employee(emp) for emp in employees], "error": None}
        
        # Regular employee can only view themselves
        employee = self.db.query(Employee).filter(Employee.id == current_user_id).first()
        if employee:
            self.rbac.log_access(current_user_id, "employee", current_user_id, "view", True)
            return {"data": [self._serialize_employee(employee)], "error": None}
        
        return {"data": [], "error": None}
    
    # ====== Task Access Methods ======
    
    def get_task(self, task_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get task details with RBAC checks."""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            return {"data": None, "error": "Task not found"}
        
        if self.rbac.can_access_task(current_user_id, task_id):
            self.rbac.log_access(current_user_id, "task", task_id, "view", True)
            return {"data": self._serialize_task(task), "error": None}
        
        self.rbac.log_access(current_user_id, "task", task_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    def get_tasks(self, current_user_id: int) -> list:
        """Get tasks with RBAC filtering."""
        tasks = self.rbac.filter_tasks_for_user(current_user_id)
        # self.rbac.log_access(current_user_id, "tasks", 0, "view_filtered", True)
        logging.debug(f"Tasks from RBAC filter: {tasks}, Type: {type(tasks)}")
        if not isinstance(tasks, list):
            logging.error(f"Expected list of tasks, got {type(tasks)}: {tasks}")
            return []
        return tasks    
    
    def create_task(self, task_data: Dict[str, Any], current_user_id: int) -> Dict[str, Any]:
        """Create a task with RBAC checks."""
        # Only managers can create tasks for others
        if task_data.get('assigned_to_id') != current_user_id:
            if not self.rbac.has_role(current_user_id, "manager") or \
               not self.rbac.has_permission(current_user_id, "assign_tasks"):
                self.rbac.log_access(current_user_id, "task", 0, "create", False)
                return {"data": None, "error": "Permission denied to assign tasks"}
            
            # Check if the assigned user is a subordinate
            assigned_user = self.db.query(Employee).filter(
                Employee.id == task_data.get('assigned_to_id')
            ).first()
            
            if not assigned_user or assigned_user.manager_id != current_user_id:
                self.rbac.log_access(current_user_id, "task", 0, "create", False)
                return {"data": None, "error": "Can only assign tasks to subordinates"}
        
        # Validate team_id
        if task_data.get('team_id'):
            team_ids = self.rbac.get_employee_teams(task_data.get('assigned_to_id'))
            if task_data.get('team_id') not in team_ids:
                self.rbac.log_access(current_user_id, "task", 0, "create", False)
                return {"data": None, "error": "Assignee is not in the specified team"}
        
        # Create the task
        task = Task(
            title=task_data.get('title'),
            description=task_data.get('description'),
            status=task_data.get('status', 'pending'),
            priority=task_data.get('priority', 'medium'),
            deadline=task_data.get('deadline'),
            assigned_to_id=task_data.get('assigned_to_id'),
            created_by_id=current_user_id,
            team_id=task_data.get('team_id')
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        self.rbac.log_access(current_user_id, "task", task.id, "create", True)
        return {"data": self._serialize_task(task), "error": None}
    
    def update_task(self, task_id: int, task_data: Dict[str, Any], current_user_id: int) -> Dict[str, Any]:
        """Update a task with RBAC checks."""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            return {"data": None, "error": "Task not found"}
        
        # Check permissions
        if task.created_by_id == current_user_id:
            # Creator can update
            pass
        elif self.rbac.has_role(current_user_id, "manager") and \
             self.rbac.is_team_manager(current_user_id, task.team_id):
            # Team manager can update
            pass
        elif task.assigned_to_id == current_user_id:
            # Assignee can only update status
            if set(task_data.keys()) - {'status'}:
                self.rbac.log_access(current_user_id, "task", task_id, "update", False)
                return {"data": None, "error": "Assignees can only update task status"}
        else:
            # No permission
            self.rbac.log_access(current_user_id, "task", task_id, "update", False)
            return {"data": None, "error": "Access denied"}
        
        # Update the task
        for key, value in task_data.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self.db.commit()
        self.db.refresh(task)
        
        self.rbac.log_access(current_user_id, "task", task_id, "update", True)
        return {"data": self._serialize_task(task), "error": None}
    
    # ====== Meeting Access Methods ======
    
    def get_meeting(self, meeting_id: str, current_user_id: int) -> Dict[str, Any]:
        """Get meeting details with RBAC checks."""
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        
        if not meeting:
            return {"data": None, "error": "Meeting not found"}
        
        if self.rbac.can_access_meeting(current_user_id, meeting_id):
            self.rbac.log_access(current_user_id, "meeting", 0, "view", True)
            return {"data": self._serialize_meeting(meeting, include_transcripts=True), "error": None}
        
        self.rbac.log_access(current_user_id, "meeting", 0, "view", False)
        return {"data": None, "error": "Access denied"}
    
    def get_meetings(self, current_user_id: int) -> Dict[str, Any]:
        """Get meetings with RBAC filtering."""
        # For HR, get all meetings
        if self.rbac.has_role(current_user_id, "hr") and \
           self.rbac.has_permission(current_user_id, "view_all_transcripts"):
            meetings = self.db.query(Meeting).all()
            self.rbac.log_access(current_user_id, "meetings", 0, "view_all", True)
            return {"data": [self._serialize_meeting(meeting) for meeting in meetings], "error": None}
        
        # Get employee data
        employee = self.db.query(Employee).filter(Employee.id == current_user_id).first()
        if not employee:
            return {"data": [], "error": "Employee not found"}
        
        # Get meetings where the employee is mentioned
        meeting_ids = self.db.query(MeetingTranscript.meeting_id)\
            .filter(MeetingTranscript.name == employee.name)\
            .distinct()\
            .all()
        meeting_ids = [mid[0] for mid in meeting_ids]
        
        # For managers, also include meetings with subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            subordinates = self.db.query(Employee)\
                .filter(Employee.manager_id == current_user_id)\
                .all()
            subordinate_names = [s.name for s in subordinates]
            
            sub_meeting_ids = self.db.query(MeetingTranscript.meeting_id)\
                .filter(MeetingTranscript.name.in_(subordinate_names))\
                .distinct()\
                .all()
            sub_meeting_ids = [mid[0] for mid in sub_meeting_ids]
            
            meeting_ids.extend(sub_meeting_ids)
            meeting_ids = list(set(meeting_ids))  # Remove duplicates
        
        meetings = self.db.query(Meeting)\
            .filter(Meeting.id.in_(meeting_ids))\
            .all()
        
        self.rbac.log_access(current_user_id, "meetings", 0, "view_filtered", True)
        return {"data": [self._serialize_meeting(meeting) for meeting in meetings], "error": None}
    
    # ====== Performance/Sentiment Access Methods ======
    
    def get_employee_skills(self, employee_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get employee skills with RBAC checks."""
        # Self-access or HR
        if employee_id == current_user_id or \
           (self.rbac.has_role(current_user_id, "hr") and self.rbac.has_permission(current_user_id, "view_all_performance")):
            skills = self.db.query(EmployeeSkills).filter(EmployeeSkills.employee_name == 
                self.db.query(Employee).filter(Employee.id == employee_id).first().name).all()
            self.rbac.log_access(current_user_id, "performance", employee_id, "view", True)
            return {"data": [self._serialize_employee_skills(s) for s in skills], "error": None}
        
        # Manager access for subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            subordinate = self.db.query(Employee).filter(Employee.id == employee_id, Employee.manager_id == current_user_id).first()
            if subordinate:
                skills = self.db.query(EmployeeSkills).filter(EmployeeSkills.employee_name == subordinate.name).all()
                self.rbac.log_access(current_user_id, "performance", employee_id, "view", True)
                return {"data": [self._serialize_employee_skills(s) for s in skills], "error": None}
        
        self.rbac.log_access(current_user_id, "performance", employee_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    def get_rolling_sentiment(self, employee_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get rolling sentiment with RBAC checks."""
        # Self-access or HR
        if employee_id == current_user_id or \
           (self.rbac.has_role(current_user_id, "hr") and self.rbac.has_permission(current_user_id, "view_all_performance")):
            sentiments = self.db.query(RollingSentiment).filter(RollingSentiment.name == 
                self.db.query(Employee).filter(Employee.id == employee_id).first().name).all()
            self.rbac.log_access(current_user_id, "performance", employee_id, "view", True)
            return {"data": [self._serialize_rolling_sentiment(s) for s in sentiments], "error": None}
        
        # Manager access for subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            subordinate = self.db.query(Employee).filter(Employee.id == employee_id, Employee.manager_id == current_user_id).first()
            if subordinate:
                sentiments = self.db.query(RollingSentiment).filter(RollingSentiment.name == subordinate.name).all()
                self.rbac.log_access(current_user_id, "performance", employee_id, "view", True)
                return {"data": [self._serialize_rolling_sentiment(s) for s in sentiments], "error": None}
        
        self.rbac.log_access(current_user_id, "performance", employee_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    # ====== Recommendation Access Methods ======
    
    def get_skill_recommendations(self, employee_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get skill recommendations with RBAC checks."""
        # Self-access or HR
        if employee_id == current_user_id or \
           (self.rbac.has_role(current_user_id, "hr") and self.rbac.has_permission(current_user_id, "view_all_recommendations")):
            recommendations = self.db.query(SkillRecommendation).filter(SkillRecommendation.name == 
                self.db.query(Employee).filter(Employee.id == employee_id).first().name).all()
            self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", True)
            return {"data": [self._serialize_skill_recommendation(r) for r in recommendations], "error": None}
        
        # Manager access for subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            subordinate = self.db.query(Employee).filter(Employee.id == employee_id, Employee.manager_id == current_user_id).first()
            if subordinate:
                recommendations = self.db.query(SkillRecommendation).filter(SkillRecommendation.name == subordinate.name).all()
                self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", True)
                return {"data": [self._serialize_skill_recommendation(r) for r in recommendations], "error": None}
        
        self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    def get_task_recommendations(self, employee_id: int, current_user_id: int) -> Dict[str, Any]:
        """Get task recommendations with RBAC checks."""
        # Self-access or HR
        if employee_id == current_user_id or \
           (self.rbac.has_role(current_user_id, "hr") and self.rbac.has_permission(current_user_id, "view_all_recommendations")):
            recommendations = self.db.query(TaskRecommendation).filter(TaskRecommendation.assigned_to == 
                self.db.query(Employee).filter(Employee.id == employee_id).first().name).all()
            self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", True)
            return {"data": [self._serialize_task_recommendation(r) for r in recommendations], "error": None}
        
        # Manager access for subordinates
        if self.rbac.has_role(current_user_id, "manager"):
            subordinate = self.db.query(Employee).filter(Employee.id == employee_id, Employee.manager_id == current_user_id).first()
            if subordinate:
                recommendations = self.db.query(TaskRecommendation).filter(TaskRecommendation.assigned_to == subordinate.name).all()
                self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", True)
                return {"data": [self._serialize_task_recommendation(r) for r in recommendations], "error": None}
        
        self.rbac.log_access(current_user_id, "recommendations", employee_id, "view", False)
        return {"data": None, "error": "Access denied"}
    
    # ====== Helper Methods for Serialization ======
    
    def _serialize_employee(self, employee: Employee) -> Dict[str, Any]:
        """Convert employee ORM object to dictionary."""
        return {
            'id': employee.id,
            'name': employee.name,
            'email': employee.email,
            'phone': employee.phone,
            'status': employee.status,
            'manager_id': employee.manager_id
        }
    
    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        """Convert task ORM object to dictionary."""
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'deadline': task.deadline.isoformat() if task.deadline else None,
            'assigned_to_id': task.assigned_to_id,
            'created_by_id': task.created_by_id,
            'team_id': task.team_id
        }
    
    def _serialize_meeting(self, meeting: Meeting, include_transcripts: bool = False) -> Dict[str, Any]:
        """Convert meeting ORM object to dictionary."""
        result = {
            'id': meeting.id,
            'title': meeting.title,
            'created_at': meeting.created_at.isoformat() if meeting.created_at else None
        }
        
        if include_transcripts:
            result['transcripts'] = [
                {
                    'id': transcript.id,
                    'name': transcript.name,
                    'text': transcript.text,
                    'processed': transcript.processed
                }
                for transcript in meeting.transcripts
            ]
            
            result['rolling_sentiments'] = [
                {
                    'id': sentiment.id,
                    'name': sentiment.name,
                    'role': sentiment.role,
                    'rolling_sentiment': sentiment.rolling_sentiment
                }
                for sentiment in meeting.rolling_sentiments
            ]
            
            result['skill_recommendations'] = [
                {
                    'id': skill.id,
                    'name': skill.name,
                    'skill_recommendation': skill.skill_recommendation
                }
                for skill in meeting.skill_recommendations
            ]
            
            result['task_recommendations'] = [
                {
                    'id': task.id,
                    'task': task.task,
                    'assigned_by': task.assigned_by,
                    'assigned_to': task.assigned_to,
                    'deadline': task.deadline,
                    'status': task.status
                }
                for task in meeting.task_recommendations
            ]
        
        return result
    
    def _serialize_employee_skills(self, skills: EmployeeSkills) -> Dict[str, Any]:
        """Convert employee skills ORM object to dictionary."""
        return {
            'id': skills.id,
            'meeting_id': skills.meeting_id,
            'employee_name': skills.employee_name,
            'role': skills.role,
            'overall_sentiment_score': skills.overall_sentiment_score
        }
    
    def _serialize_rolling_sentiment(self, sentiment: RollingSentiment) -> Dict[str, Any]:
        """Convert rolling sentiment ORM object to dictionary."""
        return {
            'id': sentiment.id,
            'meeting_id': sentiment.meeting_id,
            'name': sentiment.name,
            'role': sentiment.role,
            'rolling_sentiment': sentiment.rolling_sentiment
        }
    
    def _serialize_skill_recommendation(self, recommendation: SkillRecommendation) -> Dict[str, Any]:
        """Convert skill recommendation ORM object to dictionary."""
        return {
            'id': recommendation.id,
            'meeting_id': recommendation.meeting_id,
            'name': recommendation.name,
            'skill_recommendation': recommendation.skill_recommendation
        }
    
    def _serialize_task_recommendation(self, recommendation: TaskRecommendation) -> Dict[str, Any]:
        """Convert task recommendation ORM object to dictionary."""
        return {
            'id': recommendation.id,
            'meeting_id': recommendation.meeting_id,
            'task': recommendation.task,
            'assigned_by': recommendation.assigned_by,
            'assigned_to': recommendation.assigned_to,
            'deadline': recommendation.deadline,
            'status': recommendation.status
        }
