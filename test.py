from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from modules.db.models import Base, Employee, Role, Permission, UserRole, RolePermission, Team, TeamMember, Task, Meeting, MeetingTranscript, RollingSentiment, EmployeeSkills, SkillRecommendation, TaskRecommendation

DATABASE_URL = "postgresql://postgres:password@192.168.10.74:5433/test_sentiment_analysis"
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
        employees = [
            Employee(id=1, name="Vivek", email="vivek@gmail.com", phone="9304034054", status="active", role="Manager", manager_id=2),
Employee(id=2, name="Aarav Shah", email="aarav.shah@example.com", phone="9876543210", status="active", role="Employee", manager_id=3),
Employee(id=3, name="Priya Iyer", email="priya.iyer@example.com", phone="9123456789", status="inactive", role="HR", manager_id=1),
Employee(id=4, name="Neha Verma", email="neha.verma@example.com", phone="9988776655", status="active", role="Manager", manager_id=2),
Employee(id=5, name="Rohit Patel", email="rohit.patel@example.com", phone="9001122334", status="active", role="Employee", manager_id=3),
Employee(id=6, name="Karan Mehta", email="karan.mehta@example.com", phone="9090909090", status="inactive", role="HR", manager_id=1),
Employee(id=7, name="Sneha Reddy", email="sneha.reddy@example.com", phone="9212345678", status="active", role="Employee", manager_id=3),
Employee(id=8, name="Ankita Das", email="ankita.das@example.com", phone="9311122233", status="active", role="Employee", manager_id=3),
Employee(id=9, name="Manoj Kumar", email="manoj.kumar@example.com", phone="9870011223", status="active", role="Manager", manager_id=2),
Employee(id=10, name="Divya Singh", email="divya.singh@example.com", phone="9323456789", status="active", role="HR", manager_id=1),
Employee(id=11, name="Rahul Jain", email="rahul.jain@example.com", phone="9012345678", status="inactive", role="Employee", manager_id=3),
Employee(id=12, name="Tanya Roy", email="tanya.roy@example.com", phone="9988001122", status="active", role="HR", manager_id=1),
Employee(id=13, name="Siddharth Rao", email="siddharth.rao@example.com", phone="9345678912", status="active", role="Manager", manager_id=2),
Employee(id=14, name="Meena Nair", email="meena.nair@example.com", phone="9456123456", status="inactive", role="Employee", manager_id=3),
Employee(id=15, name="Ajay Mishra", email="ajay.mishra@example.com", phone="9876540987", status="active", role="HR", manager_id=1),
Employee(id=16, name="Writer/Director", email="writer@gmail.com", phone="9323456789", status="active", role="Manager", manager_id=2),
Employee(id=17, name="Creative Director", email="creative.director@gmail.com", phone="9876543210", status="active", role="Manager", manager_id=2),
Employee(id=18, name="Participant", email="Participant@gmail.com", phone="9323456789", status="active", role="Employee", manager_id=3),
Employee(id=19, name="Product Manager", email="writer@gmail.com", phone="9323456789", status="active", role="Manager", manager_id=2),
Employee(id=20, name="Client Lead", email="client_lead.director@gmail.com", phone="9876543210", status="active", role="Manager", manager_id=2),
Employee(id=21, name="Angie", email="angi@gmail.com", phone="9403435412", status="active", role="Employee", manager_id=3),


        ]
        db.add_all(employees)

        # Roles
        roles = [Role(id=1, name="hr"), Role(id=2, name="manager"), Role(id=3, name="employee")]
        db.add_all(roles)

#         # Permissions (adjust IDs to match your real model)
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

#         # User roles
        user_roles = [
            UserRole(employee_id=1, role_id=1),
            UserRole(employee_id=2, role_id=2),
            UserRole(employee_id=3, role_id=3),
            UserRole(employee_id=4, role_id=3),
            UserRole(employee_id=5, role_id=3),
        ]
        db.add_all(user_roles)

#         # Role permissions
        role_permissions = [
            RolePermission(role_id=1, permission_id=i) for i in [1, 7, 9, 11]
        ] + [
            RolePermission(role_id=2, permission_id=i) for i in [2, 5, 6, 8, 10, 12]
        ] + [
            RolePermission(role_id=3, permission_id=i) for i in [3, 4, 8, 10, 12]
        ]
        db.add_all(role_permissions)

#         # Teams
        teams = [Team(id=1, name="Development"), Team(id=2, name="Sales")]
        db.add_all(teams)

#         # Team members
        team_members = [
            TeamMember(team_id=1, employee_id=2, is_manager=True),
            TeamMember(team_id=1, employee_id=3, is_manager=False),
            TeamMember(team_id=1, employee_id=4, is_manager=False),
            TeamMember(team_id=2, employee_id=5, is_manager=False),
        ]
        db.add_all(team_members)

#         # Tasks
#         tasks = [
#             Task(id=1, title="Bug Fix", description="Fix login bug", priority="high", status="pending",
#                  assigned_to_id=3, created_by_id=2, team_id=1, created_at=datetime.now(), deadline=datetime(2025, 4, 25)),
#             Task(id=2, title="API Docs", description="Document API", priority="medium", status="in_progress",
#                  assigned_to_id=4, created_by_id=2, team_id=1, created_at=datetime.now(), deadline=datetime(2025, 4, 26)),
#             Task(id=3, title="Client Outreach", description="Follow up with clients", priority="low", status="pending",
#                  assigned_to_id=5, created_by_id=2, team_id=2, created_at=datetime.now(), deadline=datetime(2025, 4, 27)),
#         ]
#         db.add_all(tasks)

#         # Meetings
#         meetings = [
#             Meeting(id="mtg001", title="Dev Sync", created_at=datetime(2025, 4, 15)),
#             Meeting(id="mtg002", title="Sales Strategy", created_at=datetime(2025, 4, 16)),
#         ]
#         db.add_all(meetings)

#         # Transcripts
#         transcripts = [
#             MeetingTranscript(meeting_id="mtg001", name="Charlie Dev", text="Discussed issue tracking", processed=True),
#             MeetingTranscript(meeting_id="mtg002", name="Eve Sales", text="Sales figures reviewed", processed=True),
#         ]
#         db.add_all(transcripts)

#         # Rolling sentiment
#         sentiments = [
#             RollingSentiment(meeting_id="mtg001", name="Charlie Dev", role="Engineer", rolling_sentiment="Positive"),
#             RollingSentiment(meeting_id="mtg002", name="Eve Sales", role="Sales", rolling_sentiment="Neutral"),
#         ]
#         db.add_all(sentiments)

#         # Skills
#         skills = [
#             EmployeeSkills(meeting_id="mtg001", employee_name="Charlie Dev", role="Engineer", overall_sentiment_score=0.85),
#             EmployeeSkills(meeting_id="mtg002", employee_name="Eve Sales", role="Sales", overall_sentiment_score=0.7),
#         ]
#         db.add_all(skills)

#         # Skill recommendations
#         skill_recs = [
#             SkillRecommendation(meeting_id="mtg001", name="Charlie Dev", skill_recommendation="Improve test coverage"),
#             SkillRecommendation(meeting_id="mtg002", name="Eve Sales", skill_recommendation="Enhance negotiation skills"),
#         ]
#         db.add_all(skill_recs)

#         # Task recommendations
#         task_recs = [
#             TaskRecommendation(meeting_id="mtg001", task="Add unit tests", assigned_by="Bob Manager",
#                                assigned_to="Charlie Dev", deadline=datetime(2025, 4, 29), status="pending"),
#             TaskRecommendation(meeting_id="mtg002", task="Prepare client pitch", assigned_by="Bob Manager",
#                                assigned_to="Eve Sales", deadline=datetime(2025, 4, 30), status="pending"),
#         ]
#         db.add_all(task_recs)

        db.commit()
        print("✅ Database populated successfully.")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to populate test data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    populate_test_data()

 