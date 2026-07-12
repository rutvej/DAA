# Admin Panel UI Design Specification

This document defines the layout grids, visual components, styling rules, and views of the React Admin Panel interface.

## 1. Grid & Global Layout

The UI utilizes a two-column layout:
- **Navigation Sidebar (Width: 260px)**: Persistent on the left side of the screen. Displays navigation links and logged-in user profile widgets.
- **Main View Canvas (Flex-1)**: Fills the remaining screen width. Contains the title header, dashboard stats grid, and detail views.

---

## 2. Visual Elements & Page Mockups

### A. Login & Register Screens
- **Layout**: Centered card overlay against a dark Slate background.
- **Form Controls**: TextInput boxes for Username and Password. Buttons for [Sign In] and [Sign Up].
- **Error Banners**: Bright Rose alerts that appear inline if credentials fail.

### B. Outage Dashboard (`DashboardPage.js`)
- **Stats Card Grid**:
  - Three card indicators: Firing Outages (Rose background), Fix Success Rate (Emerald background), Firing Alerts (Indigo background).
- **Incident Activity List**:
  - A table of active incidents. Clicking an incident row routes the SRE operator to the corresponding `/fixes/{id}` details view.

### C. Live Fix details & Diff Viewer (`FixViewerPage.js`)
- **Surgical Code Diff**:
  - Code diffs are rendered using split or unified panes with syntax highlighting.
  - Deletions are shown in soft red `#fee2e2` with `-` markers.
  - Additions are shown in soft green `#dcfce7` with `+` markers.
- **Audit Logs Term Terminal**:
  - Consists of a dark background console wrapper with a monospace font.
  - Shows pulsing icons indicating that the agent is currently diagnosing the incident.
  - Appends formatted markdown strings.
- **Approval Call-to-Action Bar**:
  - Positioned at the top or bottom of the fix view.
  - Includes an **[Approve & Merge]** button (triggers code push to main branch) and a **[Reject & Re-run]** button (wipes fix state and enqueues a retry job).

### D. System Health Check (`SystemHealthPage.js`)
- **Status Cards**: Grid of components for Backend, Postgres, RabbitMQ, and MCP Server.
- **Indicators**:
  - Green dot: Active, healthy.
  - Yellow dot: Throttled or in warning (e.g. SQLite database not in WAL mode).
  - Red dot: Disconnected or down.