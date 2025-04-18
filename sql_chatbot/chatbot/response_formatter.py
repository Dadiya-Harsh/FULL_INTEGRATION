from typing import Optional, Dict, List, Any, Union
import json
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

import os
from dotenv import load_dotenv

load_dotenv()

class ResponseFormatter:
    """Formats SQL query results into natural language responses."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the response formatter.
        
        Args:
            openai_api_key: Optional API key for OpenAI
        """
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,  # Slight creativity for natural-sounding responses
            api_key=openai_api_key,
        )
        self.parser = StrOutputParser()
        
    def _prepare_result_for_llm(self, result: Union[str, pd.DataFrame, List, Dict]) -> str:
        """Convert various result formats to a string representation."""
        if isinstance(result, pd.DataFrame):
            # Convert DataFrame to JSON string representation
            if len(result) > 10:
                # Limit large results
                preview = result.head(10).to_dict(orient='records')
                return f"First 10 rows of {len(result)} total results: {json.dumps(preview, default=str)}"
            else:
                return result.to_json(orient='records', date_format='iso')
        elif isinstance(result, (list, dict)):
            # Convert list/dict to JSON string
            return json.dumps(result, default=str)
        else:
            # Return as is if already string or other format
            return str(result)
            
    def format_response(self, question: str, query: str, result: Any, 
                       error: Optional[str] = None) -> str:
        """
        Format query results into natural language response.
        
        Args:
            question: Original natural language question
            query: SQL query that was executed
            result: Query execution result
            error: Any error message (if query failed)
            
        Returns:
            Natural language response to the user's question
        """
        # Prepare result in string format
        result_str = self._prepare_result_for_llm(result) if result is not None else "No results returned."
        
        # Create response formatting prompt
        response_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful database assistant that explains SQL query results clearly.
            
            Given a user's question, the SQL query that was run to answer it, and the query results, 
            provide a natural, conversational response that directly answers their question.
            
            Guidelines:
            - Be concise but thorough
            - Highlight the most important information first
            - Include specific numbers and facts from the results
            - If relevant, mention interesting patterns or insights in the data
            - Format numbers nicely (e.g., use commas for thousands)
            - If there was an error, explain what might have gone wrong in simple terms
            - Your response should be self-contained and not reference "the query" or "the results"
            """),
            ("human", """
            User question: {question}
            
            SQL query used: {query}
            
            Query result: {result}
            
            Error (if any): {error}
            
            Please provide a helpful response:
            """)
        ])
        
        # Create chain for response generation
        response_chain = response_prompt | self.llm | self.parser
        
        try:
            # Generate formatted response
            response = response_chain.invoke({
                "question": question,
                "query": query,
                "result": result_str,
                "error": error if error else "None"
            })
            
            return response
            
        except Exception as e:
            # Fallback response if formatting fails
            if error:
                return f"I encountered an error: {error}"
            elif result is None or (isinstance(result, (list, pd.DataFrame)) and len(result) == 0):
                return "I couldn't find any data matching your query."
            else:
                return f"I found some results but had trouble formatting them clearly. Here's the raw data: {result_str[:1000]}"
    
    def generate_chart_recommendation(self, question: str, query: str, 
                                     result: pd.DataFrame) -> Optional[Dict]:
        """
        Generate chart recommendations for visualizing the data.
        
        Args:
            question: Original question
            query: SQL query
            result: DataFrame with query results
            
        Returns:
            Dict with chart recommendations or None
        """
        if not isinstance(result, pd.DataFrame) or result.empty or len(result.columns) < 2:
            return None
            
        # Create chart recommendation prompt
        chart_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data visualization expert. Based on the user's question and query results,
            recommend the best chart type to visualize this data.
            
            Return a JSON object with these fields:
            {
              "chart_type": "bar|line|pie|scatter|table",
              "x_axis": "column name for x-axis",
              "y_axis": "column name for y-axis",
              "title": "suggested chart title"
            }
            
            Only suggest a chart if it would be meaningful for the data.
            """),
            ("human", """
            User question: {question}
            
            SQL query: {query}
            
            DataFrame columns: {columns}
            
            Number of rows: {row_count}
            
            Sample data (first 5 rows): {sample}
            
            Recommend chart configuration as JSON:
            """)
        ])
        
        try:
            # Create JSON output parser
            chart_chain = chart_prompt | self.llm | self.parser
            
            # Generate chart recommendation
            recommendation = chart_chain.invoke({
                "question": question,
                "query": query,
                "columns": list(result.columns),
                "row_count": len(result),
                "sample": result.head(5).to_dict(orient='records')
            })
            
            # Parse JSON response
            try:
                chart_config = json.loads(recommendation)
                return chart_config
            except:
                return None
        
        except Exception:
            return None