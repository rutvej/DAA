# System Health Feature - UI Design

This document outlines the UI design for the System Health feature of the Admin Panel.

## Layout

The System Health page will have a simple layout, consisting of a list or a set of cards, with each item representing a single microservice.

## Components

### Service Status List/Cards

-   **Appearance:** Each service will be displayed in its own card or list item. The background color of the card will change based on the status of the service (e.g., green for "Online", red for "Offline").
-   **Content:** Each card will display:
    -   The name of the service.
    -   Its current status, in large, easy-to-read text.
    -   The timestamp of the last health check.

## Wireframe

```mermaid
graph TD
    subgraph System Health
        subgraph Services
            A("Backend API<br/>Status: Online<br/>Last Checked: 2 minutes ago")
            B("Worker Service<br/>Status: Online<br/>Last Checked: 2 minutes ago")
            C("Database<br/>Status: Online<br/>Last Checked: 2 minutes ago")
            D("LLM Service<br/>Status: Degraded<br/>Last Checked: 2 minutes ago")
        end
        E[Refresh Button]
    end

    style A fill:#d4edda,stroke:#c3e6cb
    style B fill:#d4edda,stroke:#c3e6cb
    style C fill:#d4edda,stroke:#c3e6cb
    style D fill:#f8d7da,stroke:#f5c6cb
