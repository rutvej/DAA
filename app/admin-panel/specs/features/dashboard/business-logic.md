# Dashboard Feature - Business Logic

This document outlines the business logic for the Dashboard feature of the Admin Panel.

## Data Loading and Refreshing

1.  **Initial Load:** When the administrator navigates to the dashboard, the frontend makes a series of asynchronous requests to the **Backend API** to fetch the necessary data.
2.  **Data Points:** The following data points are fetched:
    -   Log statistics (pending, in-progress, completed).
    -   A list of the 10 most recent logs.
    -   The health status of all microservices.
3.  **Automatic Refresh:** The dashboard is configured to automatically refresh the data at a regular interval (e.g., every 30 seconds) to ensure that the information is always up-to-date.

## User Interactions

-   **Viewing Log Details:** Clicking on a log in the "Recent Activity" list navigates the administrator to the detailed view of that log.
-   **Navigating to Health Page:** A "View Details" link in the "Service Status" section takes the administrator to the dedicated System Health page for a more in-depth view.

## Error Handling

-   **API Errors:** If the **Backend API** is unavailable or returns an error, the dashboard will display a clear error message to the user.
-   **Data Loading Indicators:** While the data is being fetched, the dashboard will display loading indicators to provide feedback to the user.