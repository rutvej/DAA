# Admin Panel Data Model Specification

This document details the React client-side states, persistent browser configurations, and frontend data models.

## 1. Persistent Browser Storage (`localStorage`)

The Admin Panel preserves user session tokens across page reloads using browser local storage keys:

- **`token`**: String holding the JWT authentication token. Passed in the `Authorization` request header on Axios calls.
- **`user`**: Stringified JSON holding user profile parameters:
  ```json
  {
    "username": "sre_operator",
    "role": "Administrator"
  }
  ```

---

## 2. Component State Schemas (React Hooks)

Client views utilize `useState()` and `useContext()` to model UI variables:

### Auth Context State
- **Variable**: `user`
- **Data Shape**: `null` (if unauthenticated) or `{ username: string, role: string }`.
- **Variable**: `token`
- **Data Shape**: `null` or `string`.

### Dashboard View State
- **Variable**: `stats`
- **Data Shape**:
  ```json
  {
    "activeIncidents": 0,
    "fixRate": 0,
    "alertsCount": 0
  }
  ```
- **Variable**: `incidentsList`
- **Data Shape**: Array of active Incident records.

### Fix Viewer State
- **Variable**: `fixDetails`
- **Data Shape**:
  ```json
  {
    "id": "uuid",
    "generatedFix": "diff content string",
    "postmortem": "markdown text string",
    "isApproved": false,
    "status": "Applied"
  }
  ```
- **Variable**: `executionLogs`
- **Data Shape**: Array of strings (each matching one log event formatted as markdown).

---

## 3. UI-Only Visual State Trees

- **Sidebar Toggle**: Boolean indicating whether the navigation panel is collapsed or visible.
- **Theme Mode**: String storing UI theme (`"dark"` or `"light"`). Defaults to `"dark"`.
- **Log Auto-Scroll Toggle**: Boolean. If true, the terminal log window automatically scrolls to the bottom when new trace logs are appended.