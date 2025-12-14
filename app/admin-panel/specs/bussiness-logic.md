# Admin Panel - Business Logic

This document outlines the business logic of the Admin Panel, detailing how administrators interact with the system and manage the error log processing workflow.

## User Authentication

1.  **Login:** Administrators log in to the Admin Panel using their credentials.
2.  **Session Management:** The Admin Panel maintains a session with the **Backend API** to ensure that the user is authenticated for all subsequent requests.

## Dashboard and Monitoring

1.  **Dashboard View:** Upon logging in, the administrator is presented with a dashboard that provides a real-time overview of the system.
2.  **Data Fetching:** The dashboard fetches data from the **Backend API** to display:
    -   The number of pending, in-progress, and completed tasks.
    -   A list of the most recent error logs.
    -   The status of the different system components.

## Log and Fix Management

1.  **Viewing Logs:** Administrators can navigate to a dedicated section to view a list of all submitted error logs.
2.  **Searching and Filtering:** The interface provides options to search for specific logs or filter them by status (e.g., "Pending", "In Progress", "Completed").
3.  **Viewing Fixes:** For completed tasks, administrators can view the details of the generated fix, including the code changes and any other relevant information.

## System Health Monitoring

1.  **Health Check:** The Admin Panel includes a section that displays the health status of the various microservices.
2.  **Status Polling:** The Admin Panel periodically polls the **Backend API** to get the latest health status of each component.