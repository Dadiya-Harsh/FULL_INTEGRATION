from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from chatbot.models.models import Base, Employee, Role, Permission, UserRole, RolePermission, Team, TeamMember, Task, Meeting, MeetingTranscript, RollingSentiment, EmployeeSkills, SkillRecommendation, TaskRecommendation

DATABASE_URL = "postgresql://postgres:password@localhost:5433/test_sentiment_analysis"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def populate_test_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Optional: clear existing data
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

        # Employees
        # employees = [
        #     Employee(id=1, name="Alice HR", email="alice@company.com", status="active"),
        #     Employee(id=2, name="Bob Manager", email="bob@company.com", status="active", manager_id=1),
        #     Employee(id=3, name="Charlie Dev", email="charlie@company.com", status="active", manager_id=2),
        #     Employee(id=4, name="Diana Dev", email="diana@company.com", status="active", manager_id=2),
        #     Employee(id=5, name="Eve Sales", email="eve@company.com", status="active", manager_id=2),
        # ]
        # db.add_all(employees)

        # Roles
        roles = [Role(id=1, name="hr"), Role(id=2, name="manager"), Role(id=3, name="employee")]
        db.add_all(roles)

        # Permissions (adjust IDs to match your real model)
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

        # User roles
        user_roles = [
            UserRole(employee_id=1, role_id=1),
            UserRole(employee_id=2, role_id=2),
            UserRole(employee_id=3, role_id=3),
            UserRole(employee_id=4, role_id=3),
            UserRole(employee_id=5, role_id=3),
        ]
        db.add_all(user_roles)

        # Role permissions
        role_permissions = [
            RolePermission(role_id=1, permission_id=i) for i in [1, 7, 9, 11]
        ] + [
            RolePermission(role_id=2, permission_id=i) for i in [2, 5, 6, 8, 10, 12]
        ] + [
            RolePermission(role_id=3, permission_id=i) for i in [3, 4, 8, 10, 12]
        ]
        db.add_all(role_permissions)

        # Teams
        teams = [Team(id=1, name="Development"), Team(id=2, name="Sales")]
        db.add_all(teams)

        # Team members
        team_members = [
            TeamMember(team_id=1, employee_id=2, is_manager=True),
            TeamMember(team_id=1, employee_id=3, is_manager=False),
            TeamMember(team_id=1, employee_id=4, is_manager=False),
            TeamMember(team_id=2, employee_id=5, is_manager=False),
        ]
        db.add_all(team_members)

        # Tasks
        # tasks = [
        #     Task(id=1, title="Bug Fix", description="Fix login bug", priority="high", status="pending",
        #          assigned_to_id=3, created_by_id=2, team_id=1, created_at=datetime.now(), deadline=datetime(2025, 4, 25)),
        #     Task(id=2, title="API Docs", description="Document API", priority="medium", status="in_progress",
        #          assigned_to_id=4, created_by_id=2, team_id=1, created_at=datetime.now(), deadline=datetime(2025, 4, 26)),
        #     Task(id=3, title="Client Outreach", description="Follow up with clients", priority="low", status="pending",
        #          assigned_to_id=5, created_by_id=2, team_id=2, created_at=datetime.now(), deadline=datetime(2025, 4, 27)),
        # ]
        # db.add_all(tasks)

        # # Meetings
        # meetings = [
        #     Meeting(id="mtg001", title="Dev Sync", created_at=datetime(2025, 4, 15)),
        #     Meeting(id="mtg002", title="Sales Strategy", created_at=datetime(2025, 4, 16)),
        # ]
        # db.add_all(meetings)

        # # Transcripts
        # transcripts = [
        #     MeetingTranscript(meeting_id="mtg001", name="Charlie Dev", text="Discussed issue tracking", processed=True),
        #     MeetingTranscript(meeting_id="mtg002", name="Eve Sales", text="Sales figures reviewed", processed=True),
        # ]
        # db.add_all(transcripts)

        # # Rolling sentiment
        # sentiments = [
        #     RollingSentiment(meeting_id="mtg001", name="Charlie Dev", role="Engineer", rolling_sentiment="Positive"),
        #     RollingSentiment(meeting_id="mtg002", name="Eve Sales", role="Sales", rolling_sentiment="Neutral"),
        # ]
        # db.add_all(sentiments)

        # # Skills
        # skills = [
        #     EmployeeSkills(meeting_id="mtg001", employee_name="Charlie Dev", role="Engineer", overall_sentiment_score=0.85),
        #     EmployeeSkills(meeting_id="mtg002", employee_name="Eve Sales", role="Sales", overall_sentiment_score=0.7),
        # ]
        # db.add_all(skills)

        # # Skill recommendations
        # skill_recs = [
        #     SkillRecommendation(meeting_id="mtg001", name="Charlie Dev", skill_recommendation="Improve test coverage"),
        #     SkillRecommendation(meeting_id="mtg002", name="Eve Sales", skill_recommendation="Enhance negotiation skills"),
        # ]
        # db.add_all(skill_recs)

        # # Task recommendations
        # task_recs = [
        #     TaskRecommendation(meeting_id="mtg001", task="Add unit tests", assigned_by="Bob Manager",
        #                        assigned_to="Charlie Dev", deadline=datetime(2025, 4, 29), status="pending"),
        #     TaskRecommendation(meeting_id="mtg002", task="Prepare client pitch", assigned_by="Bob Manager",
        #                        assigned_to="Eve Sales", deadline=datetime(2025, 4, 30), status="pending"),
        # ]
        # db.add_all(task_recs)

        db.commit()
        print("✅ Database populated successfully.")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to populate test data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    populate_test_data()
