# DAA Global UI Design Specification

This document defines the interface pages, layout structure, color schemes, and states of the React Admin Panel.

## 1. Design System & Theme
- **Background**: Dark mode default (Slate `#0f172a`, Zinc `#18181b`).
- **Primary Accent**: Emerald `#10b981` (for successful resolutions) and Rose `#f43f5e` (for active incidents).
- **Secondary Accent**: Indigo `#6366f1` (for SRE action items / buttons).
- **Fonts**: Inter, JetBrains Mono (for tracebacks and code diffs).

---

## 2. Layout Structure

The interface utilizes a persistent sidebar layout for authenticated users.

```
+-------------------------------------------------------------+
| Sidebar        | Dashboard / Main Content Area              |
|                |                                            |
| [DAA v3.0]     | [Stats: Firing Incidents, Fix Success Rate] |
| - Dashboard    |                                            |
| - Incidents    | +----------------------------------------+ |
| - Logs         | | Incident List Table                    | |
| - Applications | |                                        | |
| - System Health| | Service    Error       Status   Action | |
| - Logout       | | checkout   RedisErr    Fix Open [View] | |
|                | +----------------------------------------+ |
+-------------------------------------------------------------+
```

---

## 3. Core Pages & Component Mockups

### A. Dashboard (`DashboardPage.js`)
- **Key Metrics**:
  - Outage Counter: Total count of unresolved anomalies.
  - Success Rate: Percent of incidents resolved without human intervention (escalated vs fixed).
  - Telemetry Volume: Activity charts of log traffic.
- **Incident Summary Table**: Displays the top 5 most frequent active incidents sorted by `occurrence_count`.

### B. Incidents Table (`IncidentsPage.js`)
- Shows a searchable list of all incidents.
- Status labels use color codes:
  - Firing/Investigating: Pulsing red.
  - Pull Request Open: Indigo badge.
  - Cooldown: Amber timer.
  - Resolved: Green check.
  - Human Required: Deep red.

### C. Code Fix & Review Page (`FixViewerPage.js`)
- **Visual Diff Component**: Employs split-pane view (red for removals, green for additions) to display the agent's proposed `generatedFix`.
- **Postmortem Renderer**: Formats the agent's Markdown report (`postmortem_md`) to show root cause analysis and prevention steps.
- **SRE Controls**:
  - **[Approve & Merge] Button**: Triggers the backend merge webhook, closing the incident.
  - **[Reject & Re-Agent] Button**: Requests a retry with additional system instructions.
  - **[Manual Escalate] Button**: Opens a Jira ticket manually.

### D. System Health (`SystemHealthPage.js`)
- Monitors the components:
  - Backend API: Status code ping.
  - RabbitMQ Queue: Count of pending messages.
  - Disk Space: Repository cache filesystem state.
  - Self-Healing Connection: Status of DAA project crash reporter link.
