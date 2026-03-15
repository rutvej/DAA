# Manual Setup Instructions

Follow these steps to set up the environment manually:

You can also use the guided demo CLI, which follows the same steps in the same order:

```bash
python3 app/demo-setup/main.py
```

1.  **Start the services:**
    ```bash
    docker-compose up -d
    ```

2.  **Create the `test-app` project in GitLab:**
    *   Go to `http://localhost:8082` in your browser.
    *   Log in with the username `root` and the password you set for `GITLAB_ROOT_PASSWORD` in the `.env` file.
    *   Create a new project named `test-app`.

3.  **Push the `test-app` to the GitLab repository:**
    ```bash
    cd app/test-app
    git init
    git remote add origin http://root:${GITLAB_ROOT_PASSWORD}@localhost:8082/root/test-app.git
    git add .
    git commit -m "Initial commit"
    git push -u origin master
    ```

4.  **Create a personal access token in GitLab:**
    *   Go to your GitLab profile settings.
    *   Go to "Access Tokens".
    *   Create a new token with the `api` scope.
    *   Copy the token.

5.  **Set the environment variables:**
    *   Create a `.env` file by copying the `.env.example` file:
        ```bash
        cp .env.example .env
        ```
    *   Open the `.env` file and add your GitLab private token and Gemini API key:
        ```
        GITLAB_PRIVATE_TOKEN=<your_gitlab_private_token>
        GEMINI_API_KEY=<your_gemini_api_key>
        GITLAB_ROOT_PASSWORD=<your_secure_password>
        POSTGRES_PASSWORD=<your_secure_password>
        ```
    *   Replace `<your_gitlab_private_token>` with the token you created in the previous step.
    *   Replace `<your_gemini_api_key>` with your Gemini API key.
    *   Replace `<your_secure_password>` with a secure password of your choice.

6.  **Restart the services:**
    ```bash
    docker-compose restart
    ```

7.  **Create a new user and get a token:**
    ```bash
    curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" -d '{"username": "testuser", "password": "testpassword"}'
    curl -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d '{"username": "testuser", "password": "testpassword"}'
    ```

8. **Send a dummy log to the backend-api:**
    ```bash
    curl -X POST "http://localhost:8000/logs/" -H "Content-Type: application/json" -H "Authorization: Bearer <your_token>" -d '{"content": "{\"message\": \"test error\"}", "app_name": "test-app"}'
    ```
