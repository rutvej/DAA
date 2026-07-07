import os
import requests
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

class CheckAlertsInput(BaseModel):
    app_name: str = Field(description="The name of the application to check alerts for.")

@tool(args_schema=CheckAlertsInput)
def check_alerts(app_name: str) -> str:
    """Checks the database/API for any active alerts for the given application.
    This helps determine if infrastructure or environmental issues are affecting the app.
    
    Args:
        app_name: The name of the application.
        
    Returns:
        A list of active alerts formatted as text, or a message indicating no alerts.
    """
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    daa_token = os.environ.get("DAA_TOKEN", "")
    url = f"{backend_url}/alerts/"
    headers = {}
    if daa_token:
        headers["Authorization"] = f"Bearer {daa_token}"
    try:
        response = requests.get(url, params={"app_name": app_name.strip(), "active_only": True}, headers=headers, timeout=10)
        response.raise_for_status()
        alerts = response.json()
        if not alerts:
            return f"No active alerts found for application '{app_name}'."
        
        output = f"Active alerts for application '{app_name}':\n"
        for alert in alerts:
            output += (
                f"- [{alert['severity'].upper()}] {alert['summary']} "
                f"(Status: {alert['status']}, Time: {alert['timestamp']})\n"
                f"  Description: {alert.get('description', 'None')}\n"
            )
        return output
    except Exception as e:
        return f"Error retrieving alerts from backend: {str(e)}"
