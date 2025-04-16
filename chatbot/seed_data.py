from models import SessionLocal, Base, engine, Employee, Task
from datetime import datetime, timedelta

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    
    # Check if there's existing data
    if db.query(Employee).count() > 0:
        print("Data already exists, skipping seed.")
        db.close()
        return
    
    # Create managers
    manager1 = Employee(
        name="Sarah Johnson",
        email="sarah@example.com",
        phone="555-1234",
        status="active",
        role="manager"
    )
    db.add(manager1)
    db.flush()  # To get the ID
    
    # Create HR
    hr1 = Employee(
        name="Michael Brown",
        email="hr@example.com",
        phone="555-5678",
        status="active",
        role="hr"
    )
    db.add(hr1)
    
    # Create employees
    emp1 = Employee(
        name="John Smith",
        email="john@example.com",
        phone="555-2345",
        status="active",
        role="employee",
        manager_id=manager1.id
    )
    emp2 = Employee(
        name="Emily Davis",
        email="emily@example.com",
        phone="555-3456",
        status="active",
        role="employee",
        manager_id=manager1.id
    )
    emp3 = Employee(
        name="Robert Wilson",
        email="robert@example.com",
        phone="555-4567",
        status="active",
        role="employee",
        manager_id=manager1.id
    )
    
    db.add_all([emp1, emp2, emp3])
    db.flush()
    
    # Create tasks
    tasks = [
        Task(
            title="Complete quarterly report",
            description="Analyze sales data and prepare quarterly report",
            status="pending",
            priority="high",
            deadline=datetime.now() + timedelta(days=7),
            assigned_to_id=emp1.id,
            created_by_id=manager1.id
        ),
        Task(
            title="Update client presentation",
            description="Add new product features to the client presentation",
            status="in_progress",
            priority="medium",
            deadline=datetime.now() + timedelta(days=3),
            assigned_to_id=emp2.id,
            created_by_id=manager1.id
        ),
        Task(
            title="Review marketing materials",
            description="Proofread and approve marketing materials for new campaign",
            status="completed",
            priority="low",
            deadline=datetime.now() - timedelta(days=1),
            assigned_to_id=emp3.id,
            created_by_id=manager1.id
        )
    ]
    db.add_all(tasks)
    
    db.commit()
    print("Seed data created successfully!")
    db.close()

if __name__ == "__main__":
    seed_data()