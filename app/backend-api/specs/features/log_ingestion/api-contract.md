# Log Ingestion Feature - API Contract

This document outlines the API contract for the Log Ingestion feature.

## Endpoints

### Log Submission

-   **`POST /logs`**
    -   **Description:** Submits a new error log for processing.
    -   **Request Body:** ` { "content": "string" } `
    -   **Response:** ` { "logId": "string", "status": "Pending" } `
