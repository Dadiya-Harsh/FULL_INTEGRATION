# -*- coding: utf-8 -*-
# app/query_classifier.py
# This module classifies user queries to determine the resource type and required permission.
from typing import Tuple, Optional

def classify_query(query_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Classify query to determine resource type and required permission."""
    query_text = query_text.lower()

    # Task queries
    if "task" in query_text or "tasks" in query_text:
        if "my tasks" in query_text or "show my tasks" in query_text:
            return "tasks", "view_own_tasks"
        if "team tasks" in query_text or "show team tasks" in query_text:
            return "tasks", "view_team_tasks"
        if "create task" in query_text or "add task" in query_text:
            return "tasks", "assign_tasks"
        return "tasks", "view_own_tasks"  # Default task permission

    # Meeting queries
    if "meeting" in query_text or "meetings" in query_text:
        if "my meetings" in query_text or "show meetings" in query_text:
            return "meetings", "view_own_transcripts"
        return "meetings", "view_own_transcripts"  # Default meeting permission

    # Employee queries
    if "employee" in query_text or "employees" in query_text or "team members" in query_text:
        if "all employees" in query_text or "list employees" in query_text:
            return "employees", "view_all_employees"
        if "my team" in query_text or "team members" in query_text:
            return "employees", "view_team_employees"
        return "employees", "view_own_employee"

    # Performance/Sentiment queries
    if "performance" in query_text or "sentiment" in query_text:
        return "performance", "view_own_performance"

    return None, None  # Unknown query