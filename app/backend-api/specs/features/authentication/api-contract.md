# Authentication Feature - API Contract

This document defines the API contract for the Authentication feature of the Backend API.

## Endpoints

-   **`POST /auth/register`**
    -   **Description:** Registers a new user.
    -   **Request Body:**
        ```json
        {
          "username": "string",
          "password": "string"
        }
        ```
    -   **Response:**
        -   **201 Created:**
            ```json
            {
              "message": "User registered successfully"
            }
            ```
        -   **400 Bad Request:** If the input is invalid or the username is already taken.

-   **`POST /auth/login`**
    -   **Description:** Authenticates a user and returns a JWT.
    -   **Request Body:**
        ```json
        {
          "username": "string",
          "password": "string"
        }
        ```
    -   **Response:**
        -   **200 OK:**
            ```json
            {
              "token": "string"
            }
            ```
        -   **401 Unauthorized:** If the credentials are invalid.