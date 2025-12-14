# Backend API - Business Logic

This document outlines the business logic of the Backend API, detailing the flow of operations for log ingestion, user authentication, and status reporting.

## Log Ingestion

1.  **Receive Log:** The API receives an error log from a client application via a POST request to the `/logs` endpoint.
2.  **Validate Input:** The API validates the incoming data to ensure it is in the correct format.
3.  **Create Database Entry:** A new entry is created in the **Database** for the log with an initial status of "Pending".
4.  **Queue Job:** The API creates a new job with the log information and sends it to the **Message Broker**.

## User Authentication

1.  **User Registration:** The API provides an endpoint for new users to register.
2.  **User Login:** Users can log in by providing their credentials to a dedicated endpoint. Upon successful authentication, the API returns a JWT.
3.  **Token Validation:** For protected endpoints, the API validates the JWT to ensure that the user is authenticated and has the necessary permissions.

## Status Reporting

1.  **Get Log Status:** The API provides an endpoint to get the status of a specific log by its ID.
2.  **List All Logs:** The API provides an endpoint to list all the logs, with support for pagination and filtering.
3.  **Get System Health:** The API provides an endpoint to get the health status of the different system components.

## Worker Service Communication

1.  **Job Submission:** The Backend API's primary interaction with the **Worker Service** is to submit jobs via the **Message Broker**.
2.  **Status Updates:** The **Worker Service** updates the status of the job directly in the **Database**. The Backend API then reads this information to report the status to the client.