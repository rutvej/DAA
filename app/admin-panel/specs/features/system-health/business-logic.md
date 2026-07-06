# System Health Feature - Business Logic

This document outlines the business logic for the System Health feature of the Admin Panel.

## Data Loading and Refreshing

1.  **Initial Load:** When the administrator navigates to the System Health page, the frontend makes a request to the `GET /health` endpoint of the **Backend API** to fetch the status of all services.
2.  **Automatic Refresh:** The page is configured to automatically refresh the data at a regular interval (e.g., every 15 seconds) to provide a near real-time view of the system's health.

## User Interactions

-   **Manual Refresh:** A "Refresh" button is provided to allow the administrator to manually trigger a health check at any time.

## Error Handling

-   **API Errors:** If the **Backend API** is unavailable or returns an error, the page will display a clear error message.
-   **Service Unhealthy:** If a service is reported as "Offline" or "Degraded", it will be highlighted in the UI to draw the administrator's attention.