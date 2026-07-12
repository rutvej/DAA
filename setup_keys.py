#!/usr/bin/env python3
import os
import shutil
import subprocess


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_input(prompt, default=None):
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"{prompt}: ").strip()


def main():
    clear_screen()
    print("==================================================")
    print("       DAA Agent Platform Onboarding Setup        ")
    print("==================================================")
    print("This script will configure your .env file, pull local LLM models,")
    print("and set up your credentials (Jira, GitHub, GitLab).\n")

    # 1. LLM Provider configuration
    print("--- 1. Select LLM Provider ---")
    print("1) Google Gemini (Recommended)")
    print("2) OpenAI")
    print("3) Ollama (Local Model)")
    provider_choice = get_input("Choose LLM Provider (1/2/3)", "1")

    provider = "google"
    model = "gemini-2.5-flash"
    api_key = ""
    base_url = ""

    if provider_choice == "2":
        provider = "openai"
        model = get_input("OpenAI Model", "gpt-4o")
        api_key = get_input("OpenAI API Key")
    elif provider_choice == "3":
        provider = "ollama"
        model = get_input("Ollama Model", "llama3")
        base_url = get_input("Ollama Base URL", "http://localhost:11434/v1")

        # Check if Ollama is running and model can be pulled
        pull_choice = get_input(
            "Would you like to pull the model automatically? (y/n)", "y"
        ).lower()
        if pull_choice == "y":
            if shutil.which("ollama"):
                print(f"Executing: ollama pull {model} ...")
                try:
                    subprocess.run(["ollama", "pull", model], check=True)
                    print(f"Successfully pulled model {model}!")
                except subprocess.CalledProcessError:
                    print(
                        "Failed to pull model automatically. Ensure Ollama is running."
                    )
            else:
                print(
                    "Ollama CLI not found in path. Please pull the model manually: 'ollama pull "
                    + model
                    + "'"
                )
    else:
        api_key = get_input("Gemini API Key")

    print("\n--- 2. Project Connections (GitLab / GitHub / Jira) ---")
    github_token = get_input("GitHub Token (Optional)")
    gitlab_token = get_input("GitLab Private Token (Optional)")
    jira_url = get_input(
        "Jira Site URL (Optional, e.g. https://your-domain.atlassian.net)"
    )
    jira_token = get_input("Jira API Token (Optional)")
    jira_project_key = get_input("Jira Project Key (Optional)")

    # Read existing .env if present
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    # Load from env.example as fallback
    if os.path.exists(".env.example"):
        with open(".env.example", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip() not in env_vars:
                        env_vars[k.strip()] = v.strip()

    # Update values
    env_vars["LLM_PROVIDER"] = provider
    env_vars["LLM_MODEL"] = model
    env_vars["LLM_BASE_URL"] = base_url
    if api_key:
        if provider == "google":
            env_vars["GEMINI_API_KEY"] = api_key
        else:
            env_vars["OPENAI_API_KEY"] = api_key
            env_vars["LLM_API_KEY"] = api_key

    if github_token:
        env_vars["GITHUB_TOKEN"] = github_token
    if gitlab_token:
        env_vars["GITLAB_PRIVATE_TOKEN"] = gitlab_token
    if jira_url:
        env_vars["JIRA_URL"] = jira_url
    if jira_token:
        env_vars["JIRA_TOKEN"] = jira_token
    if jira_project_key:
        env_vars["JIRA_PROJECT_KEY"] = jira_project_key

    # Save to .env
    with open(".env", "w") as f:
        f.write("# DAA Configured Environment Variables\n")
        for k, v in sorted(env_vars.items()):
            f.write(f"{k}={v}\n")

    print("\n==================================================")
    print("Setup Complete! .env file written successfully.")
    print("You can now build and launch the platform using:")
    print("docker-compose up --build -d")
    print("==================================================")


if __name__ == "__main__":
    main()
