# Backend API - System Overview

The Backend API is the central component of the system, responsible for handling all incoming requests from the client applications (Admin Panel, SDKs, and Cloud integrations), managing the workflow of error log processing, and providing status updates.

## Key Responsibilities

-   **Log Ingestion:** Receives error logs and queues them for processing. Supports webhook ingestion from major cloud logging services.
-   **Workflow Orchestration:** Interacts with the **Message Broker** to send jobs to the **Worker Service**.
-   **Status Management:** Tracks the status of each job and provides updates to the clients.
-   **Data Persistence:** Communicates with the **Database** to store logs, fixes, project connections, and active alerts.
-   **Authentication and Authorization:** Secures the API and ensures that only authorized users can access resources.
-   **Project Connection management:** Allows users to link repositories (GitHub/GitLab) and Jira settings dynamically.
-   **Alert Ingestion:** Receives active system/infrastructure alerts to correlate with application failures.

## Technology Stack

-   **Framework:** Python with FastAPI.
-   **Database:** PostgreSQL.
-   **Message Broker:** RabbitMQ.
-   **Authentication:** JWT (JSON Web Tokens).

## Architecture

The Backend API is a stateless service that exposes a set of RESTful endpoints. It is designed to be horizontally scalable and deployable to container-based cloud platforms like Google Cloud Run, AWS ECS, or Azure Container Apps via automated Terraform blueprints.

## Dynamic LLM and Local Model Support

Instead of a single hardcoded LLM, the platform supports multiple LLMs:
- **Google Gemini** (via API key)
- **OpenAI** (via API key)
- **Ollama / Local Models** (Llama3, Mistral, etc., pulled locally during initial setup)

## Automated Testing & Remediation Verification

To ensure code changes do not break target codebases, the agent runs tests locally using a dynamic `run_tests` runner tool and iterates on code improvements.

## Postmortem & Remediation Reports

On success, the agent generates:
1. A Git Pull Request containing the proposed fix.
2. A comprehensive markdown **Postmortem Report** summarizing the issue, root cause, alert correlation, fix details, test verification, and future prevention steps. Users can view and download this report with a single click.

