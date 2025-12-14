# Backend API - System Overview

The Backend API is the central component of the system, responsible for handling all incoming requests from the client applications (Admin Panel and potentially other clients), managing the workflow of error log processing, and providing status updates.

## Key Responsibilities

-   **Log Ingestion:** Receives error logs and queues them for processing.
-   **Workflow Orchestration:** Interacts with the **Message Broker** to send jobs to the **Worker Service**.
-   **Status Management:** Tracks the status of each job and provides updates to the clients.
-   **Data Persistence:** Communicates with the **Database** to store and retrieve information.
-   **Authentication and Authorization:** Secures the API and ensures that only authorized users can access the resources.

## Technology Stack

-   **Framework:** Node.js with Express.js, Python with FastAPI, or Go with Gin.
-   **Database:** PostgreSQL or MongoDB.
-   **Message Broker:** RabbitMQ or Redis.
-   **Authentication:** JWT (JSON Web Tokens).

## Architecture

The Backend API is a stateless service that exposes a set of RESTful endpoints. It is designed to be horizontally scalable to handle a large number of requests. It communicates with the other components of the system (Database, Message Broker) to perform its tasks.

## Worker Service Communication

The Backend API communicates with the **Worker Service** via a **Message Broker**. When a new log is submitted, the Backend API creates a new job and sends it to the **Message Broker**. The **Worker Service** then picks up the job, processes it, and updates the status of the log in the **Database**. The Backend API can then read the status of the log from the **Database** and report it to the client.