# This script populates the database with test data for the sentiment analysis application.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Employee, Role, Permission, UserRole, RolePermission, Team, TeamMember, Task, Meeting, MeetingTranscript, RollingSentiment, EmployeeSkills, SkillRecommendation, TaskRecommendation
from datetime import datetime

# Database configuration
DATABASE_URL = "postgresql://postgres:password@192.168.10.74:5433/test1"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def populate_test_data():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Clear existing data (optional)
        db.query(TaskRecommendation).delete()
        db.query(SkillRecommendation).delete()
        db.query(EmployeeSkills).delete()
        db.query(RollingSentiment).delete()
        db.query(MeetingTranscript).delete()
        db.query(Meeting).delete()
        db.query(Task).delete()
        db.query(TeamMember).delete()
        db.query(Team).delete()
        db.query(RolePermission).delete()
        db.query(UserRole).delete()
        db.query(Permission).delete()
        db.query(Role).delete()
        db.query(Employee).delete()
        db.commit()

        # Insert Employees
        employees = [
            # Employee(id=1, name="Alice Admin", email="alice@company.com", phone="123-456-7890", status="active", manager_id=None),
            # Employee(id=2, name="Bob Manager", email="bob@company.com", phone="123-456-7891", status="active", manager_id=1),
            # Employee(id=3, name="Charlie Worker", email="charlie@company.com", phone="123-456-7892", status="active", manager_id=2),
            Employee(id=4, name="Diana Worker", email="diana@company.com", phone="123-456-7893", status="active", manager_id=2),
            Employee(id=5, name="Eve Worker", email="eve@company.com", phone="123-456-7894", status="active", manager_id=2),
        ]
        db.add_all(employees)

        # Insert Roles
        roles = [
            Role(id=1, name="hr"),
            Role(id=2, name="manager"),
            Role(id=3, name="employee"),
        ]
        db.add_all(roles)

        # Insert Permissions
        permissions = [
            Permission(id=1, name="view_all_employees", resource_type="employees"),
            Permission(id=2, name="view_team_employees", resource_type="employees"),
            Permission(id=3, name="view_own_employee", resource_type="employees"),
            Permission(id=4, name="view_own_tasks", resource_type="tasks"),
            Permission(id=5, name="view_team_tasks", resource_type="tasks"),
            Permission(id=6, name="assign_tasks", resource_type="tasks"),
            Permission(id=7, name="view_all_transcripts", resource_type="meetings"),
            Permission(id=8, name="view_own_transcripts", resource_type="meetings"),
            Permission(id=9, name="view_all_performance", resource_type="performance"),
            Permission(id=10, name="view_own_performance", resource_type="performance"),
            Permission(id=11, name="view_all_recommendations", resource_type="recommendations"),
            Permission(id=12, name="view_own_recommendations", resource_type="recommendations"),
        ]
        db.add_all(permissions)

        # Insert UserRoles
        user_roles = [
            UserRole(employee_id=1, role_id=1),  # Alice: hr
            UserRole(employee_id=2, role_id=2),  # Bob: manager
            UserRole(employee_id=3, role_id=3),  # Charlie: employee
            UserRole(employee_id=4, role_id=3),  # Diana: employee
            UserRole(employee_id=5, role_id=3),  # Eve: employee
        ]
        db.add_all(user_roles)

        # Insert RolePermissions
        role_permissions = [
            RolePermission(role_id=1, permission_id=1),
            RolePermission(role_id=1, permission_id=7),
            RolePermission(role_id=1, permission_id=9),
            RolePermission(role_id=1, permission_id=11),
            RolePermission(role_id=2, permission_id=2),
            RolePermission(role_id=2, permission_id=5),
            RolePermission(role_id=2, permission_id=6),
            RolePermission(role_id=2, permission_id=8),
            RolePermission(role_id=2, permission_id=10),
            RolePermission(role_id=2, permission_id=12),
            RolePermission(role_id=3, permission_id=3),
            RolePermission(role_id=3, permission_id=4),
            RolePermission(role_id=3, permission_id=8),
            RolePermission(role_id=3, permission_id=10),
            RolePermission(role_id=3, permission_id=12),
        ]
        db.add_all(role_permissions)

        # Insert Teams
        teams = [
            Team(id=1, name="Dev Team"),
            Team(id=2, name="Sales Team"),
        ]
        db.add_all(teams)

        # Insert TeamMembers
        team_members = [
            TeamMember(employee_id=2, team_id=1, is_manager=True),
            TeamMember(employee_id=3, team_id=1, is_manager=False),
            TeamMember(employee_id=4, team_id=1, is_manager=False),
            TeamMember(employee_id=5, team_id=2, is_manager=False),
        ]
        db.add_all(team_members)

        # Insert Tasks
        tasks = [
            Task(id=1, title="Fix Bug #123", description="Debug login issue", status="pending", priority="high",
                 created_at=datetime(2025, 4, 15, 10, 0), deadline=datetime(2025, 4, 20, 17, 0),
                 assigned_to_id=3, created_by_id=2, team_id=1),
            Task(id=2, title="Update Docs", description="Revise API docs", status="in_progress", priority="medium",
                 created_at=datetime(2025, 4, 14, 9, 0), deadline=datetime(2025, 4, 18, 17, 0),
                 assigned_to_id=4, created_by_id=2, team_id=1),
            Task(id=3, title="Sales Report", description="Prepare Q1 report", status="pending", priority="low",
                 created_at=datetime(2025, 4, 15, 11, 0), deadline=datetime(2025, 4, 25, 17, 0),
                 assigned_to_id=5, created_by_id=2, team_id=2),
            Task(id=4, title="Review Code", description="Review PR #456", status="done", priority="medium",
                 created_at=datetime(2025, 4, 13, 8, 0), deadline=datetime(2025, 4, 16, 17, 0),
                 assigned_to_id=3, created_by_id=3, team_id=1),
        ]
        db.add_all(tasks)

        # Insert Meetings
        meetings = [
            Meeting(id="mtg_001", title="Sprint Planning", created_at=datetime(2025, 4, 10, 9, 0)),
            Meeting(id="mtg_002", title="Sales Review", created_at=datetime(2025, 4, 12, 14, 0)),
        ]
        db.add_all(meetings)

        # Insert MeetingTranscripts
        transcripts = [
            MeetingTranscript(id=1, meeting_id="mtg_001", name="Charlie Worker", text="Charlie discussed bug fixes...", processed=True),
            MeetingTranscript(id=2, meeting_id="mtg_001", name="Diana Worker", text="Diana reviewed documentation updates...", processed=True),
            MeetingTranscript(id=3, meeting_id="mtg_002", name="Eve Worker", text="Eve presented sales figures...", processed=True),
        ]
        db.add_all(transcripts)

        # Insert RollingSentiment
        sentiments = [
            RollingSentiment(id=1, meeting_id="mtg_001", name="Charlie Worker", role="Engineer", rolling_sentiment="Positive"),
            RollingSentiment(id=2, meeting_id="mtg_001", name="Diana Worker", role="Engineer", rolling_sentiment="Neutral"),
            RollingSentiment(id=3, meeting_id="mtg_002", name="Eve Worker", role="Sales", rolling_sentiment="Positive"),
        ]
        db.add_all(sentiments)

        # Insert EmployeeSkills
        skills = [
            EmployeeSkills(id=1, meeting_id="mtg_001", employee_name="Charlie Worker", role="Engineer", overall_sentiment_score=0.8),
            EmployeeSkills(id=2, meeting_id="mtg_001", employee_name="Diana Worker", role="Engineer", overall_sentiment_score=0.6),
            EmployeeSkills(id=3, meeting_id="mtg_002", employee_name="Eve Worker", role="Sales", overall_sentiment_score=0.9),
        ]
        db.add_all(skills)

        # Insert SkillRecommendations
        skill_recommendations = [
            SkillRecommendation(id=1, meeting_id="mtg_001", name="Charlie Worker", skill_recommendation="Learn advanced debugging"),
            SkillRecommendation(id=2, meeting_id="mtg_001", name="Diana Worker", skill_recommendation="Improve technical writing"),
            SkillRecommendation(id=3, meeting_id="mtg_002", name="Eve Worker", skill_recommendation="Advanced sales techniques"),
        ]
        db.add_all(skill_recommendations)

        # Insert TaskRecommendations
        task_recommendations = [
            TaskRecommendation(id=1, meeting_id="mtg_001", task="Debug new feature", assigned_by="Bob Manager",
                               assigned_to="Charlie Worker", deadline=datetime(2025, 4, 20, 17, 0), status="pending"),
            TaskRecommendation(id=2, meeting_id="mtg_001", task="Write user guide", assigned_by="Bob Manager",
                               assigned_to="Diana Worker", deadline=datetime(2025, 4, 22, 17, 0), status="pending"),
            TaskRecommendation(id=3, meeting_id="mtg_002", task="Follow up clients", assigned_by="Bob Manager",
                               assigned_to="Eve Worker", deadline=datetime(2025, 4, 25, 17, 0), status="pending"),
        ]
        db.add_all(task_recommendations)

        # Commit changes
        db.commit()
        print("Test data populated successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error populating test data: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    populate_test_data()
