# Log Ingestion Feature - Business Logic

This document outlines the business logic for the Log Ingestion feature of the Backend API.

## Log Submission Workflow

1.  **Receive Log:** The API receives a new error log via a `POST` request to the `/logs` endpoint.
2.  **Authenticate Request:** The API verifies the JWT in the `Authorization` header to identify the user who is submitting the log.
3.  **Validate Input:** The API validates the request body to ensure that it contains a non-empty `content` field.
4.  **Create Log Entry:** A new record is created in the `Logs` table in the **Database**. The log is given a default status of "Pending" and is associated with the authenticated user.
5.  **Create Job:** A new job is created with the ID of the log and its content.
6.  **Publish to Message Broker:** The job is published to a specific queue in the **Message Broker** to be consumed by the **Worker Service**.
7.  **Return Response:** The API returns a response to the client with the ID of the newly created log and its "Pending" status.