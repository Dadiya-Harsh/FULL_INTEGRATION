# -*- coding: utf-8 -*-
# app/utils.py
# This module contains utility functions for formatting and serializing query results.
from typing import List, Dict, Any

def format_response(data: List[Dict[str, Any]], resource_type: str) -> str:
    """Format query results as a natural language response."""
    if not data:
        return "No results found."

    if resource_type == "tasks":
        return "\n".join(
            f"Task {d['id']}: {d['title']} (Status: {d['status']}, Priority: {d['priority']})"
            for d in data
        )
    elif resource_type == "meetings":
        return "\n".join(
            f"Meeting {d['id']}: {d['title']} (Created: {d['created_at']})"
            for d in data
        )
    elif resource_type == "employees":
        return "\n".join(
            f"Employee {d['id']}: {d['name']} (Email: {d['email']})"
            for d in data
        )
    return str(data)

def serialize_result(data, resource_type: str):
    """
    Ensure Consitency of output.
    """
    if isinstance(data, dict) and 'data' in data:
        return data['data']  # Extract the data list directly
    elif isinstance(data, str):
        try:
            import json
            return json.loads(data)
        except json.JSONDecodeError:
            return {"error": "Invalid data format"}
    return data
