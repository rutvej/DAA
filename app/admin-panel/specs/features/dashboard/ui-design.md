# Dashboard Feature - UI Design

This document outlines the UI design for the Dashboard feature of the Admin Panel.

## Layout

The dashboard will have a multi-column layout, with different sections for each type of information.

-   **Top Row:** A row of "stat cards" that provide a quick summary of the key metrics.
-   **Main Content Area:** A two-column layout with the "Recent Activity" feed on the left and the "Service Status" on the right.

## Components

### Stat Cards

-   **Appearance:** Each card will have a title, a large number representing the metric, and a brief description.
-   **Content:**
    -   "Pending Logs"
    -   "In-Progress Logs"
    -   "Completed Logs"
    -   "Failed Logs"

### Recent Activity Feed

-   **Appearance:** A list or table that displays the most recent logs.
-   **Content:** Each item in the feed will show the log's ID, a snippet of its content, and its current status (represented by a color-coded badge).

### Service Status

-   **Appearance:** A list of the microservices with a status indicator for each.
-   **Content:** Each item will show the name of the service and its current status (e.g., "Online", "Offline"). A green dot will indicate a healthy service, and a red dot will indicate a problem.

## Wireframe

```mermaid
graph TD
    subgraph Dashboard
        subgraph Header
            A[Logo]
            B[User Name]
            C[Logout]
        end
        subgraph Stats
            D[Pending: 10]
            E[In-Progress: 5]
            F[Completed: 50]
            G[Failed: 2]
        end
        subgraph Main Content
            subgraph Recent Activity
                H["Log #123 - Null Pointer Exception (In-Progress)"]
                I["Log #122 - File Not Found (Completed)"]
                J["Log #121 - Database Connection Error (Failed)"]
            end
            subgraph Service Status
                K["Backend API: Online"]
                L["Worker Service: Online"]
                M["Database: Online"]
            end
        end
    end