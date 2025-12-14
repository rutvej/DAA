# Log Ingestion Feature - Data Model

This document outlines the data models for the Log Ingestion feature.

## Log

Represents a single error log submitted to the system.

-   `id` (string): A unique identifier for the log.
-   `userId` (string): The ID of the user who submitted the log.
-   `status` (string): The current status of the log (e.g., "Pending", "In Progress", "Completed", "Failed").
-   `timestamp` (datetime): The time the log was submitted.
-   `content` (text): The full content of the error log.