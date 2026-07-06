# Authentication Feature - Business Logic

This document outlines the business logic for the Authentication feature of the Backend API.

## User Registration

1.  **Receive Registration Request:** The API receives a request to the `POST /auth/register` endpoint with a username and password.
2.  **Validate Input:** The API validates the input to ensure that the username is not already taken and that the password meets the required complexity criteria.
3.  **Hash Password:** The user's password is an salted and hashed using a strong hashing algorithm.
4.  **Create User:** A new user is created in the **Database** with the provided username, the hashed password, and a default `role` of "Admin".

## User Login

1.  **Receive Login Request:** The API receives a request to the `POST /auth/login` endpoint with a username and password.
2.  **Verify User:** The API retrieves the user from the **Database** by their username.
3.  **Verify Password:** The API compares the provided password with the stored hash.
4.  **Generate JWT:** If the password is correct, the API generates a new JWT that contains the user's ID and role.
5.  **Return Token:** The JWT is returned to the client.

## Token Verification

1.  **Receive Request:** For any protected endpoint, the API expects a JWT in the `Authorization` header.
2.  **Validate Token:** The API verifies the signature and the expiration date of the token.
3.  **Authorize User:** If the token is valid, the API extracts the user's information from the token and grants them access to the requested resource.