# -*- coding: utf-8 -*-
# app/chatbot_handler.py
import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sql_agent_tool import SQLAgentTool
from chatbot.services.data_access import DataAccessLayer
from chatbot.services.rbac_service import RBACService
from chatbot.app.query_classifier import classify_query
from chatbot.app.utils import format_response, serialize_result
import logging

class ChatbotHandler:
    def __init__(self, db_session: Session, sql_agent: SQLAgentTool):
        self.db = db_session
        self.sql_agent = sql_agent
        self.data_access = DataAccessLayer(db_session)
        self.rbac = RBACService(db_session)

    def process_query(self, query_text: str, employee_id: int) -> Dict[str, Any]:
        """
        Process a natural language query with RBAC (Role-Based Access Control) checks.
        
        Args:
            query_text (str): The natural language query from the user.
            employee_id (int): The ID of the employee making the query.
        
        Returns:
            Dict[str, Any]: A dictionary containing the status, message, and data (if applicable).
        """
        from datetime import datetime  # Ensure proper import

        # Step 1: Get user context
        user_context = self.rbac.get_user_context(employee_id)
        if not user_context.get("employee_id"):
            return {"status": "error", "message": "Employee not found"}

        # Step 2: Classify query to determine resource and permission
        resource_type, permission_name = classify_query(query_text)
        if not resource_type or not permission_name:
            logging.warning("LLM is not able to understand your query, please try to be specific with your tasks.")
            return {
                "status": "error",
                "message": "Unable to understand query. Please try a different phrasing."
            }

        # Step 3: Check if the user has the required permission
        if not self.rbac.has_permission(employee_id, permission_name, resource_type):
            self.rbac.log_access(employee_id, resource_type, 0, "view", False)
            logging.error("You don't have access or enough permission")
            return {
                "status": "error",
                "message": f"You don't have permission to {permission_name} {resource_type}"
            }

        # Step 4: Process the query with the SQL agent tool
        try:
            # Inject user context into the query
            context_query = f"{query_text} (user_id: {employee_id}, roles: {','.join(user_context['roles'])}, teams: {','.join(map(str, self.rbac.get_employee_teams(employee_id)))})"
            result = self.sql_agent.process_natural_language_query(context_query)
            print(f"Raw Result from sql-agent-tool: {result}")
            logging.info(f"Raw result from sql-agent-tool: {result}")

            # Step 5: Validate the structure of result.data
            if not isinstance(result.data, list):
                logging.error(f"Unexpected result.data type: {type(result.data)}. Data: {result.data}")
                return {"status": "error", "message": "Unexpected response format from SQL Agent"}
            
            # Additional validation: Ensure each item in the list is a dictionary
            serialized_data = []
            for row in result.data:
                # Debugging log for value types
                for key, value in row.items():
                    logging.debug(f"Key: {key}, Value: {value}, Type: {type(value)}")
                
                # Serialize datetime objects to ISO 8601 strings
                serialized_row = {
                    key: (value.isoformat() if isinstance(value, datetime) else value)
                    for key, value in row.items()
                }
                serialized_data.append(serialized_row)
            
            # Step 6: Handle empty dataset
            if len(serialized_data) == 0:
                logging.info("No results found in the query.")
                return {"status": "success", "message": "No results found.", "data": []}

            # Step 7: Check if the query execution was successful
            if not result.success:
                logging.error("Query generation has failed.")
                self.rbac.log_access(employee_id, resource_type, 0, "view", False)
                return {"status": "error", "message": "Query failed: " + str(result.error)}

            # Step 8: Filter results using DataAccessLayer
            filtered_data = self._filter_results(serialized_data, resource_type, employee_id)
            self.rbac.log_access(employee_id, resource_type, 0, "view", True)
            logging.info("SQL query has been generated and run successfully.")
            return {
                "status": "success",
                "message": f"Found {len(filtered_data)} results",
                "data": serialize_result(filtered_data, resource_type)
            }
        
        # except Exception as e:
        #     logging.exception("Error processing query")
        #     self.rbac.log_access(employee_id, resource_type, 0, "view", False)
        #     return {"status": "error", "message": f"Error processing query: {str(e)}"}
        except Exception as e:
            self.db.rollback()  # 🔥 Add this line to reset the transaction state
            logging.exception("Error processing query")
            self.rbac.log_access(employee_id, resource_type, 0, "view", False)
            return {"status": "error", "message": f"Error processing query: {str(e)}"}
        finally:
            self.db.close()  # Optional if you're done with the session



    def _filter_results(self, data: list, resource_type: str, employee_id: int) -> list:
        """Filter sql-agent-tool results to ensure RBAC compliance."""
        if not isinstance(data, list):
            logging.error(f"Expected list, got {type(data)}. Data: {data}")
            return []

        # Ensure each row is a dictionary
        for row in data:
            if not isinstance(row, dict):
                logging.error(f"Invalid row format: {row}")
                return []

        if resource_type == "tasks":
            authorized_tasks = self.data_access.get_tasks(employee_id)
            logging.debug(f"Authorized tasks: {authorized_tasks}, Type: {type(authorized_tasks)}")

            # Ensure authorized_tasks is a list of Task objects
            if not isinstance(authorized_tasks, list):
                logging.error(f"Expected list of tasks from get_tasks, got {type(authorized_tasks)}: {authorized_tasks}")
                return []

            # Extract task IDs (attribute-style access)
            authorized_ids = {task.id for task in authorized_tasks}
            return [row for row in data if row.get("id") in authorized_ids]

        return data  # Default: return unfiltered (extend for other resources)