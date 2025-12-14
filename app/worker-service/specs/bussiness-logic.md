# Worker Service - Business Logic

This document outlines the business logic of the Worker Service, detailing the step-by-step process of handling an error log and generating a fix.

## Job Processing Workflow

1.  **Consume Job:** The Worker Service continuously listens for new jobs on the **Message Broker**. When a new job arrives, it is consumed by one of the available worker instances.
2.  **Update Status:** The first step in processing is to update the status of the corresponding log in the **Database** to "In Progress".
3.  **Parse Log:** The worker parses the error log to extract key information, such as the error message, stack trace, and any other relevant context.
4.  **Prepare LLM Prompt:** Based on the parsed information, the worker constructs a detailed prompt to send to the **LLM**. This prompt will include the error log, and any relevant code snippets or context.
5.  **Send to LLM:** The worker sends the prompt to the **LLM** and waits for a response.
6.  **Process LLM Response:** When the **LLM** returns a response, the worker processes it to extract the generated fix.
7.  **Store Fix:** The worker creates a new entry in the `Fixes` table in the **Database** to store the generated solution.
8.  **Update Final Status:** The worker updates the status of the log in the **Database** to "Completed".

## Error Handling

-   **LLM Errors:** If the **LLM** fails to generate a fix or returns an error, the worker will update the log status to "Failed" and record the error details in the database.
-   **Job Failures:** If a job fails for any other reason, the worker will implement a retry mechanism with an exponential backoff strategy. If the job continues to fail after a certain number of retries, it will be marked as "Failed".