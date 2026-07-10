# Backend API Support for UI Design

This document details how the Backend API serves layout metrics and handles dynamic CORS policies for the Admin Panel.

## 1. Dynamic CORS Middleware

To allow the Admin Panel to run on local Developer workstations or SRE dashboard terminals across local LAN networks, the Backend API implements a dynamic CORS validation middleware in [main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L40-L71):

```python
@app.middleware("http")
async def dynamic_cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    ...
```

### Middleware Logic
1. Reads HTTP request header `Origin`.
2. Parses the hostname of the Origin.
3. Queries the `Application` table to find an application whose `allowed_ip` matches the Origin hostname.
4. If a match is found:
   - For `OPTIONS` requests: Short-circuits the pipeline and returns a response containing permissive CORS headers (`Access-Control-Allow-Origin: <origin>`, `Access-Control-Allow-Credentials: true`, `Access-Control-Allow-Methods: *`, `Access-Control-Allow-Headers: *`).
   - For other methods: Completes request handling and appends the CORS headers to the response.

---

## 2. UI-Specific Data Endpoints

The backend provides several endpoints built specifically to supply frontend views:

### Dashboard Stats (`GET /dashboard`)
- **Controller**: `/home/rutvej/Desktop/DAA/app/backend-api/src/routers/dashboard.py`
- **Output Fields**:
  - `active_incidents` (count of firing issues)
  - `total_incidents` (historic volume)
  - `fix_rate_percent` (remediated percentage: `fixed_incidents / total_resolved`)
  - `active_alerts` (active infra alerts)
  - `recent_incidents` (chronological list)

### Incidents Query (`GET /incidents`)
- **Controller**: `/home/rutvej/Desktop/DAA/app/backend-api/src/routers/incidents.py`
- **Utility**: Feeds the incident tracker lists. Paginated and filterable by status (`investigating`, `pr_open`, `cooldown`, etc.).

### Fix Details (`GET /fixes/{id}`)
- **Controller**: `/home/rutvej/Desktop/DAA/app/backend-api/src/routers/fixes.py`
- **Utility**: Fetches the unified patch diff text and the postmortem markdown report, rendered as HTML on the frontend.
- **Log Stream (`GET /fixes/{id}/logs`)**: Feeds the real-time agent execution trace log viewer in the React UI.

### System Health Dashboard (`GET /status`)
- **Controller**: `/home/rutvej/Desktop/DAA/app/backend-api/src/routers/status.py`
- **Utility**: Queries container states and service statuses (API, Postgres, RabbitMQ, MCP).
