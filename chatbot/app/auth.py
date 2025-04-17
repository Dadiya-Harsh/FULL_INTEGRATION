# -*- coding: utf-8 -*-
# app/auth.py   
from sqlalchemy.orm import Session
from modules.db.models import Employee, SessionLocal

def authenticate_user(email: str, password: str) -> int | None:
    """Authenticate user and return employee_id if valid."""
    # In production, use proper password hashing and verification
    # This is a simplified example
    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.email == email).first()
        if employee and password == "root":  # Replace with secure check
            return employee.id
        return None
    finally:
        db.close()
