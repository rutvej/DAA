# Admin Panel System Overview

This document provides a software architecture overview and folder structure specification for the React Admin Panel interface.

## 1. Application Architecture

The Admin Panel is a single-page application built with React, located under `/home/rutvej/Desktop/DAA/app/admin-panel/`.

```
app/admin-panel/
├── package.json         # React project configuration & dependency list
├── nginx.conf           # Web server routing configuration for builds
├── public/              # Static public assets
│   ├── index.html       # Root HTML shell
│   └── manifest.json    # PWA configuration
├── src/
│   ├── index.js         # Entry point mounting App component
│   ├── App.js           # Core router definition and path configurations
│   ├── App.css          # Global styling rules
│   ├── services/
│   │   └── api.js       # Axios client encapsulating Backend API communication
│   ├── contexts/
│   │   └── AuthContext.js # Global User Authentication and JWT state provider
│   └── pages/           # Page View components
│       ├── LoginPage.js
│       ├── RegisterPage.js
│       ├── DashboardPage.js
│       ├── ApplicationsPage.js
│       ├── IncidentsPage.js
│       ├── LogsPage.js
│       ├── LogDetailsPage.js
│       ├── FixViewerPage.js
│       └── SystemHealthPage.js
```

---

## 2. Global State & Context Providers

- **Authentication State (`AuthContext.js`)**:
  - Manages logging user credentials, storing JWT tokens, and managing active sessions.
  - Automatically loads tokens from browser `localStorage` on page loads.
  - Attaches Bearer authentication headers dynamically to Axios HTTP instances.
- **Routing Engine (`App.js`)**:
  - Uses `react-router-dom` to manage Client-Side routing.
  - Implements route protection: unauthenticated queries redirect to the `/login` view, while authenticated queries load SRE workspace dashboards.

---

## 3. Communication Layer (`services/api.js`)

All interactions with the FastAPI backend flow through [services/api.js](file:///home/rutvej/Desktop/DAA/app/admin-panel/src/services/api.js).
- Configures a base Axios client pointing to `REACT_APP_API_URL` (passed as build arguments to Nginx).
- Intercepts requests to inject headers:
  ```javascript
  api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  ```
- Exposes clean HTTP promise functions (e.g. `getIncidents()`, `getFix(id)`, `approveFix(id)`).