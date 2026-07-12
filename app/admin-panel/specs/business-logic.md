# Admin Panel Business Logic Specification

This document details the user authentication lifecycle, live log polling engines, and SRE resolution controls in the Admin Panel application.

## 1. User Authentication Lifecycle (`AuthContext.js`)

Authentication state is managed by the context provider [AuthContext.js](file:///home/rutvej/Desktop/DAA/app/admin-panel/src/contexts/AuthContext.js):

- **Login Action**:
  1. Operator submits credentials via `LoginPage.js`.
  2. Context executes `POST /auth/login` to backend.
  3. If authenticated (HTTP 200), saves the access token and user role to `localStorage` and updates context state.
  4. Triggers routing shift to `/dashboard`.
- **Session Restoration**:
  1. On reload, the root `index.js` mounts the provider, which reads `localStorage.getItem('token')`.
  2. If the token is found, context states are re-populated, avoiding forcing the user to sign back in.
- **Logout Action**:
  1. Clears local storage keys.
  2. Resets state variables to `null`.
  3. Redirects to the login route.

---

## 2. Live Log Polling Engine

When the SRE opens the fix page for an incident currently being investigated:
- **Polling Loop**: The view executes `GET /fixes/{id}/logs` every 2 seconds inside a React `useEffect` hook.
- **Deduplication & Rendering**:
  - The component checks incoming array lines against current state arrays.
  - New lines are appended and parsed using a Markdown component.
  - Triggers a DOM reference scroll operation `element.scrollIntoView({ behavior: 'smooth' })` to keep the latest agent steps in view.
- **Loop Termination**: The polling timer is cleared when the backend incident status transitions to `"resolved"`, `"cooldown"`, or `"human_required"`.

---

## 3. SRE Approval and Remediation Dispatches

In `FixViewerPage.js`, the SRE interacts with the agent's proposed resolutions:

- **Approve Action**:
  - Clicking the **[Approve & Merge]** button triggers `api.post(`/fixes/${id}/approve`)`.
  - The UI locks input buttons, displays a loading spinner, and waits for a response.
  - On HTTP 200 success, the UI displays the merge pull request link and updates the incident status to `"resolved"`.
- **Reject / Re-Run Action**:
  - SRE can request the agent retry the diagnosis by submitting instructions (e.g. "Try checking file headers").
  - Dispatches a request to reset the fix record and queue a new background task.
- **Manual Escalate Action**:
  - Skips automated remediation, requesting the backend generate a Jira ticket.