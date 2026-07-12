# Admin Panel Infrastructure & Deployment Specification

This document details the web server configuration, container compilation stages, and build variables of the Admin Panel.

## 1. Container Configuration & Dockerfile

The React app container is compiled using a multi-stage Docker build defined in `/home/rutvej/Desktop/DAA/app/admin-panel/Dockerfile`.

### Stage 1: Compilation
- **Image**: `node:18-alpine` (lightweight NodeJS environment).
- **Process**:
  1. Copies `package.json` and runs `npm install`.
  2. Injects the build argument `REACT_APP_API_URL`.
  3. Executes `npm run build` to generate compiled static assets in `/app/build/`.

### Stage 2: Web Server Serving
- **Image**: `nginx:1.21-alpine` (lightweight web server).
- **Process**:
  1. Copies static files from Stage 1 (`/app/build/`) to `/usr/share/nginx/html/`.
  2. Copies a custom `nginx.conf` configuration file to `/etc/nginx/conf.d/default.conf`.

---

## 2. Nginx Router Setup (`nginx.conf`)

Because React employs client-side virtual routing (`react-router-dom`), the web server must serve `index.html` for any unmatched path queries to prevent HTTP 404 errors on browser page reloads:

```nginx
server {
    listen 5002;
    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }
}
```

- **Container Port**: Configured to listen on port `5002` internally.
- **Host Port Mapping**: Mapped to host port `5003` in `docker-compose.yml`.

---

## 3. Build & Runtime Environment Variables

- **`REACT_APP_API_URL`**: Used by the Axios client. Injected during container build time:
  ```bash
  docker build --build-arg REACT_APP_API_URL=http://localhost:8000 -t daa-admin-panel .
  ```
  In standard Compose setups, the client IP address (such as `http://192.168.1.41:8000` or `http://localhost:8000`) is injected.
