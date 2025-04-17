# -*- coding: utf-8 -*-
# app/services/rbac_service.py
from sqlalchemy.orm import Session
from typing import List, Optional, Union, Dict, Any
from modules.db.models import Employee, Role, Permission, RolePermission, UserRole, TeamMember, Task, Meeting, MeetingTranscript, AccessLog

class RBACService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_user_context(self, employee_id: int) -> Dict[str, Any]:
        """Get user context information including roles and teams."""
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            return {"error": "Employee not found"}
        
        # Get roles
        roles = self.db.query(Role)\
            .join(UserRole, Role.id == UserRole.role_id)\
            .filter(UserRole.employee_id == employee_id)\
            .all()
        role_names = [role.name for role in roles]
        
        # Get teams
        team_ids = self.get_employee_teams(employee_id)
        
        return {
            "employee_id": employee.id,
            "name": employee.name,
            "roles": role_names,
            "team_ids": team_ids,
            "is_manager": "manager" in role_names,
            "is_hr": "hr" in role_names
        }
    
    def get_user_roles(self, employee_id: int) -> List[Role]:
        """Get all roles assigned to a user."""
        user_roles = self.db.query(Role)\
            .join(UserRole, Role.id == UserRole.role_id)\
            .filter(UserRole.employee_id == employee_id)\
            .all()
        return user_roles
    
    def get_user_permissions(self, employee_id: int) -> List[Permission]:
        """Get all permissions for a user based on their roles."""
        permissions = self.db.query(Permission)\
            .join(RolePermission, Permission.id == RolePermission.permission_id)\
            .join(UserRole, RolePermission.role_id == UserRole.role_id)\
            .filter(UserRole.employee_id == employee_id)\
            .all()
        return permissions
    
    def has_permission(self, employee_id: int, permission_name: str, resource_type: Optional[str] = None) -> bool:
        """Check if a user has a specific permission."""
        query = self.db.query(Permission)\
            .join(RolePermission, Permission.id == RolePermission.permission_id)\
            .join(UserRole, RolePermission.role_id == UserRole.role_id)\
            .filter(UserRole.employee_id == employee_id)\
            .filter(Permission.name == permission_name)
        
        if resource_type:
            query = query.filter(Permission.resource_type == resource_type)
        
        return query.first() is not None
    
    def has_role(self, employee_id: int, role_name: str) -> bool:
        """Check if a user has a specific role."""
        return self.db.query(UserRole)\
            .join(Role, UserRole.role_id == Role.id)\
            .filter(UserRole.employee_id == employee_id)\
            .filter(Role.name == role_name)\
            .first() is not None
    
    def is_team_manager(self, employee_id: int, team_id: int) -> bool:
        """Check if an employee is a manager of a specific team."""
        return self.db.query(TeamMember)\
            .filter(TeamMember.employee_id == employee_id)\
            .filter(TeamMember.team_id == team_id)\
            .filter(TeamMember.is_manager == True)\
            .first() is not None
    
    def get_employee_teams(self, employee_id: int) -> List[int]:
        """Get all team IDs an employee belongs to."""
        team_members = self.db.query(TeamMember)\
            .filter(TeamMember.employee_id == employee_id)\
            .all()
        return [tm.team_id for tm in team_members]
    
    def log_access(self, employee_id: int, resource_type: str, resource_id: int, 
                   action: str, success: bool = True) -> None:
        """Log an access attempt."""
        log = AccessLog(
            employee_id=employee_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            success=success
        )
        self.db.add(log)
        self.db.commit()
    
    def can_access_task(self, employee_id: int, task_id: int, action: str = "view") -> bool:
        """Check if a user can access a specific task."""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False
        
        # Check if user is the assignee
        if task.assigned_to_id == employee_id:
            return True
        
        # Check if user is the creator
        if task.created_by_id == employee_id:
            return True
        
        # Check if user is a manager of the team the task belongs to
        if task.team_id and self.is_team_manager(employee_id, task.team_id):
            return True
        
        # Check if user is HR and has view permission
        if action == "view" and self.has_role(employee_id, "hr") and \
           self.has_permission(employee_id, "view_all_employees"):
            return True
        
        return False
    
    def can_access_meeting(self, employee_id: int, meeting_id: str) -> bool:
        """Check if a user can access a specific meeting."""
        # HR can access all meetings
        if self.has_role(employee_id, "hr") and self.has_permission(employee_id, "view_all_transcripts"):
            return True
        
        # Check if user is mentioned in meeting transcripts
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            return False
        
        # Check if employee is in meeting transcript
        transcript_with_employee = self.db.query(MeetingTranscript)\
            .filter(MeetingTranscript.meeting_id == meeting_id)\
            .filter(MeetingTranscript.name == employee.name)\
            .first()
        
        if transcript_with_employee:
            return True
        
        # Manager can access transcripts of their team members
        if self.has_role(employee_id, "manager"):
            # Get subordinates
            subordinates = self.db.query(Employee)\
                .filter(Employee.manager_id == employee_id)\
                .all()
            subordinate_names = [s.name for s in subordinates]
            
            # Check if any subordinate is in the meeting
            transcript_with_subordinate = self.db.query(MeetingTranscript)\
                .filter(MeetingTranscript.meeting_id == meeting_id)\
                .filter(MeetingTranscript.name.in_(subordinate_names))\
                .first()
            
            if transcript_with_subordinate:
                return True
        
        return False
    
    def filter_tasks_for_user(self, employee_id: int) -> List[Task]:
        """Get all tasks a user can access."""
        # Get user roles
        roles = [role.name for role in self.get_user_roles(employee_id)]
        
        if "hr" in roles:
            # HR can see all tasks
            return self.db.query(Task).all()
        
        if "manager" in roles:
            # Manager can see own tasks and tasks of team members
            team_ids = self.get_employee_teams(employee_id)
            managed_team_ids = [
                tm.team_id for tm in self.db.query(TeamMember)
                .filter(TeamMember.employee_id == employee_id)
                .filter(TeamMember.is_manager == True)
                .all()
            ]
            
            return self.db.query(Task).filter(
                (Task.assigned_to_id == employee_id) |
                (Task.created_by_id == employee_id) |
                (Task.team_id.in_(managed_team_ids))
            ).all()
        
        # Regular employee can only see their assigned tasks
        return self.db.query(Task).filter(
            (Task.assigned_to_id == employee_id) | 
            (Task.created_by_id == employee_id)
        ).all()
