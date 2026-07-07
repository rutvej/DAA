# Python Agent System Overview

## 1. Introduction

The Python Agent is an AI agent that is responsible for analyzing code, identifying root causes of errors, and automatically generating pull requests with suggested fixes. The agent is built using a modular architecture that allows for easy extension and customization.

## 2. Key Features

-   **Modular Architecture**: The agent is composed of a set of tools that can be easily added, removed, or modified.
-   **Langchain Integration**: The agent uses the Langchain library to orchestrate the execution of the tools and to interact with large language models (LLMs).
-   **Pydantic Models**: The agent uses Pydantic models to define the inputs and outputs of the tools, ensuring data consistency and validation.
-   **Automated Code Fixing**: The agent can automatically apply fixes to the code, create a new branch, commit the changes, and create a pull request.
-   **Database Integration**: The agent updates the database with the status of the analysis and the URL of the pull request.
-   **Model Context Protocol (MCP) Integration**: The agent dynamically registers tools from external database or cloud-based MCP servers (e.g. Postgres, BigQuery) defined in `mcp_config.json`, and prefers them over direct APIs when applicable.

## 3. Architecture

The Python Agent is a standalone service that is deployed as a Docker container. The agent is triggered by the Daa backend API when a new error log is received. The agent then uses the Langchain library to create a chain of tools that are executed in a specific order to analyze the error and generate a fix.

The agent is composed of the following components:

-   **Agent**: The main component of the agent that is responsible for orchestrating the execution of the tools.
-   **Tools**: A set of tools that the agent can use to perform specific tasks, such as fetching the git repository, analyzing the code, applying the fix, creating a pull request, and updating the database.
-   **MCP Client**: Simple MCP client that automatically spawns and manages external stdio-based MCP servers (e.g. BigQuery MCP) as defined in `mcp_config.json`, loading their tools into the agent's runtime.
-   **Pydantic Models**: A set of Pydantic models that define the inputs and outputs of the tools.
-   **Langchain**: The Langchain library that is used to create the chain of tools and to interact with the LLM.
-   **LLM**: The agent will use the Gemini API as its large language model.
