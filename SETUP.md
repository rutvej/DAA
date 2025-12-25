# Manual Setup Instructions

Follow these steps to set up the environment manually:

1.  **Start the services:**
    ```bash
    docker-compose up -d
    ```

2.  **Create the `test-app` project in GitLab:**
    *   Go to `http://localhost:8082` in your browser.
    *   Log in with the username `root` and the password `yoursecurepassword`.
    *   Create a new project named `test-app`.

3.  **Push the `test-app` to the GitLab repository:**
    ```bash
    cd app/test-app
    git init
    git remote add origin http://root:yoursecurepassword@localhost:8082/root/test-app.git
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
    *   Create a `.env` file in the root of the project.
    *   Add the following lines to the `.env` file:
        ```
        GITLAB_PRIVATE_TOKEN=<your_gitlab_private_token>
        GEMINI_API_KEY=<your_gemini_api_key>
        ```
    *   Replace `<your_gitlab_private_token>` with the token you created in the previous step.
    *   Replace `<your_gemini_api_key>` with your Gemini API key.

6.  **Restart the services:**
    ```bash
    docker-compose restart
    ```
