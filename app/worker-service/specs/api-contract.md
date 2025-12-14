# Worker Service - API Contract

The Worker Service is a background processing service and does not expose a public API. It consumes jobs from the **Message Broker** and communicates with the **Database** and the **LLM**.

## Incoming Jobs

The Worker Service listens for jobs on a specific queue in the **Message Broker**. The format of the job message is as follows:

-   **`job` message:**
    -   **`logId`** (string): The ID of the log to be processed.
    -   **`logContent`** (string): The full content of the error log.

## Outgoing Communication

-   **Database:** The Worker Service communicates with the **Database** to update the status of logs and store the generated fixes.
-   **LLM:** The Worker Service sends prompts to the **LLM** to generate fixes.