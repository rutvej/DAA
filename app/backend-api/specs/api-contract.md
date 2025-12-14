# Backend API - API Contract

This document defines the API contract for the Backend API, detailing the available endpoints, the expected request and response formats, and the authentication requirements.

## Authentication

All endpoints, unless otherwise specified, require a valid JWT to be included in the `Authorization` header of the request.

---

## Endpoints

### Authentication

-   **`POST /auth/register`**
    -   **Description:** Registers a new user.
    -   **Request Body:** ` { "username": "string", "password": "string" } `
    -   **Response:** ` { "message": "User registered successfully" } `

-   **`POST /auth/login`**
    -   **Description:** Authenticates a user and returns a JWT.
    -   **Request Body:** ` { "username": "string", "password": "string" } `
    -   **Response:** ` { "token": "string" } `

### Logs

-   **`POST /logs`**
    -   **Description:** Submits a new error log for processing.
    -   **Request Body:** ` { "content": "string" } `
    -   **Response:** ` { "logId": "string", "status": "Pending" } `

-   **`GET /logs`**
    -   **Description:** Retrieves a list of all logs.
    -   **Query Parameters:** `page`, `limit`, `status`
    -   **Response:** ` [ { "id": "string", "status": "string", "timestamp": "datetime" } ] `

-   **`GET /logs/{id}`**
    -   **Description:** Retrieves the details of a specific log.
    -   **Response:** ` { "id": "string", "status": "string", "timestamp": "datetime", "content": "string" } `

### Status Reporting

-   **`GET /status/{id}`**
    -   **Description:** Retrieves the status of a specific log by its ID.
    -   **Response:** ` { "status": "string" } `

### Fixes

-   **`GET /fixes/{id}`**
    -   **Description:** Retrieves the details of a specific fix.
    -   **Response:** ` { "id": "string", "logId": "string", "timestamp": "datetime", "generatedFix": "string" } `

### System Health

-   **`GET /health`**
    -   **Description:** Retrieves the health status of the system's components.
    -   **Response:** ` [ { "serviceName": "string", "status": "string" } ] `