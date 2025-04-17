# -*- coding: utf-8 -*-
# app/chatbot_handler.py
from typing import Dict, Any
from sqlalchemy.orm import Session
from sql_agent_tool import SQLAgentTool
from services.data_access import DataAccessLayer
from services.rbac_service import RBACService
from app.query_classifier import classify_query
from app.utils import format_response, serialize_result

class ChatbotHandler:
    def __init__(self, db_session: Session, sql_agent: SQLAgentTool):
        self.db = db_session
        self.sql_agent = sql_agent
        self.data_access = DataAccessLayer(db_session)
        self.rbac = RBACService(db_session)

    def process_query(self, query_text: str, employee_id: int) -> Dict[str, Any]:
        """Process a natural language query with RBAC checks."""
        # Get user context
        user_context = self.rbac.get_user_context(employee_id)
        if not user_context.get("employee_id"):
            return {"status": "error", "message": "Employee not found"}

        # Classify query to determine resource and permission
        resource_type, permission_name = classify_query(query_text)
        if not resource_type or not permission_name:
            return {
                "status": "error",
                "message": "Unable to understand query. Please try a different phrasing."
            }

        # Check permission
        if not self.rbac.has_permission(employee_id, permission_name, resource_type):
            self.rbac.log_access(employee_id, resource_type, 0, "view", False)
            return {
                "status": "error",
                "message": f"You don't have permission to {permission_name} {resource_type}"
            }

        # Process query with sql-agent-tool
        try:
            # Inject user context into query
            context_query = f"{query_text} (user_id: {employee_id}, roles: {','.join(user_context['roles'])}, teams: {','.join(map(str, self.rbac.get_employee_teams(employee_id)))})"
            result = self.sql_agent.process_natural_language_query(context_query)
            if not result.success:
                self.rbac.log_access(employee_id, resource_type, 0, "view", False)
                return {"status": "error", "message": "Query failed: " + str(result.error)}

            # Filter results using DataAccessLayer
            filtered_data = self._filter_results(result.data, resource_type, employee_id)
            self.rbac.log_access(employee_id, resource_type, 0, "view", True)
            return {
                "status": "success",
                "message": f"Found {len(filtered_data)} results",
                "data": serialize_result(filtered_data, resource_type)
            }
        except Exception as e:
            self.rbac.log_access(employee_id, resource_type, 0, "view", False)
            return {"status": "error", "message": f"Error processing query: {str(e)}"}

    def _filter_results(self, data: list, resource_type: str, employee_id: int) -> list:
        """Filter sql-agent-tool results to ensure RBAC compliance."""
        if resource_type == "tasks":
            authorized_tasks = self.data_access.get_tasks(employee_id)
            authorized_ids = {task["id"] for task in authorized_tasks}
            return [row for row in data if row.get("id") in authorized_ids]
        elif resource_type == "meetings":
            authorized_meetings = self.data_access.get_meetings(employee_id)
            authorized_ids = {meeting["id"] for meeting in authorized_meetings}
            return [row for row in data if row.get("id") in authorized_ids]
        elif resource_type == "employees":
            authorized_employees = self.data_access.get_employees(employee_id)
            authorized_ids = {emp["id"] for emp in authorized_employees}
            return [row for row in data if row.get("id") in authorized_ids]
        return data  # Default: return unfiltered (extend for other resources)