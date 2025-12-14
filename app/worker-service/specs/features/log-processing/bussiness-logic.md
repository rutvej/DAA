# Log Processing Feature - Business Logic

This document outlines the business logic for the Log Processing feature of the Worker Service.

## Step-by-Step Workflow

1.  **Consume Job:** A worker instance consumes a job from the `log_processing` queue in the **Message Broker**.
2.  **Acknowledge Message:** The worker acknowledges the message to prevent it from being redelivered.
3.  **Update Log Status:** The worker updates the status of the log in the **Database** to "In Progress".
4.  **Prepare LLM Prompt:** The worker constructs a detailed prompt for the **LLM**, including the full content of the error log.
5.  **Call LLM:** The worker makes a request to the **LLM** with the prepared prompt.
6.  **Handle LLM Response:**
    -   **Success:** If the LLM returns a valid fix, the worker saves the fix to the `Fixes` table in the **Database**.
    -   **Failure:** If the LLM returns an error or an invalid response, the worker logs the error and proceeds to the next step.
7.  **Update Final Status:**
    -   **Success:** The worker updates the status of the log to "Completed".
    -   **Failure:** The worker updates the status of the log to "Failed".

## Retry Logic

-   If the LLM call fails due to a transient issue (e.g., network error), the worker can be configured to retry the request a certain number of times before marking the job as failed.