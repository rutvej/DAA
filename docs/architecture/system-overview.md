# System Overview & Architecture

DAA employs a three-phase hybrid pipeline for autonomous incident resolution.

## Architectural Flow

```mermaid
flowchart TD
    Start([Application Error]) --> Ingest[Backend API Ingestion :8080/8000]
    Ingest --> Dedup{Deduplication & Policies}
    Dedup -->|Under Threshold| Drop[Log & Ignore]
    Dedup -->|Over Threshold| Queue[RabbitMQ / Sync Queue]
    Queue --> AgentTriage[Agent 4-Dimension Investigation]
    AgentTriage --> HITLCheck{DAA_HITL_MODE}
    HITLCheck -->|true| UI[React Admin Panel UI]
    UI --> CreatePR
    HITLCheck -->|false| CreatePR[Open Pull/Merge Request via Git Provider API]
```

## Modes of Operation

1. **Standalone (Serverless Edge)**: Runs purely in a single container. Great for Cloud Run. Internal communication is synchronous.
2. **Distributed Scale-Out (Compose)**: Uses separate containers for the React Admin Panel, Postgres Database, RabbitMQ, and the Agent worker.

## Core Services

- **backend-api**: FastAPI ingestion engine that receives telemetry and enforces cooldowns.
- **python-agent**: Langchain ReAct loop with a hard 8-call budget cap. Uses AST grep tools.
- **admin-panel**: A Human-in-the-Loop review dashboard to approve PRs before they are opened.
