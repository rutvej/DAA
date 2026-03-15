# Quickstart

## Prerequisites
- Docker and Docker Compose
- A Google Gemini API key

## Steps
1. Create `.env` from template:
   ```bash
   cp .env.example .env
   ```
2. Fill in required values in `.env` (GitLab password/token, Gemini key, Postgres password).
3. Start services:
   ```bash
   docker-compose up -d
   ```
4. Create the `test-app` project in GitLab:
   - Open `http://localhost:8082`.
   - Log in as `root` using `GITLAB_ROOT_PASSWORD` from `.env`.
   - Create a project named `test-app`.
5. Push the `test-app` code to GitLab:
   ```bash
   cd app/test-app
   git init
   git remote add origin http://root:${GITLAB_ROOT_PASSWORD}@localhost:8082/root/test-app.git
   git add .
   git commit -m "Initial commit"
   git push -u origin master
   ```
6. Create a GitLab personal access token with `api` scope and set `GITLAB_PRIVATE_TOKEN` in `.env`.
7. Create a backend user and get a token:
   ```bash
   curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" -d '{"username": "testuser", "password": "testpassword"}'
   curl -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d '{"username": "testuser", "password": "testpassword"}'
   ```
8. Set `DAA_TOKEN` in `.env` to the JWT returned from login.
9. Send a dummy log to verify ingestion:
   ```bash
   curl -X POST "http://localhost:8000/logs/" -H "Content-Type: application/json" -H "Authorization: Bearer <your_token>" -d '{"content": "{\"message\": \"test error\"}", "app_name": "test-app"}'
   ```

## Admin Panel
- Open `http://localhost:5003`.
- Register and log in using the UI.
