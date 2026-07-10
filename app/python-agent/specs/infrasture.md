# Python Agent Infrastructure Specification

This document details the Docker configuration, filesystem mounts, and configuration files of the Python Agent container.

## 1. Container Configuration & Dockerfile

The python agent container is built from `/home/rutvej/Desktop/DAA/app/python-agent/Dockerfile`.

### Base Image
- **Image**: `python:3.11-slim`
- **System Packages**:
  - `git`: Crucial for git cache checkouts, remote branch validations, worktree prunes, commits, and pushes.
  - `patch`: Standard Linux patch utility to apply code fixes to workspace files.

---

## 2. Docker Compose Mounts & Integrations

The agent requires access to local filesystems, docker sockets, and credentials to execute its diagnostic routines. The following volumes are mounted in [docker-compose.yml](file:///home/rutvej/Desktop/DAA/docker-compose.yml#L53-L84):

1. **Docker Socket Mount (`/var/run/docker.sock:/var/run/docker.sock`)**:
   Allows the agent to view running containers or run container diagnostic checks.
2. **Local Git Workspace (`${DAA_GIT_DIR:-/home/rutvej/Desktop/DAA/.git}:/app/.git:ro`)**:
   Mounts the primary workspace git metadata in read-only mode to retrieve workspace statuses.
3. **Agy CLI Executor (`/home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro`)**:
   Mounts the local `agy` CLI binary to allow `AgyChatModel` to run LLM completions via command line.
4. **Gemini Configuration (`/home/rutvej/.gemini:/root/.gemini:ro`)**:
   Provides default credentials files for accessing Vertex/Google Cloud services.
5. **Codex Authentication Credentials (`${CODEX_AUTH_JSON_PATH:-/home/rutvej/snap/codex/34/auth.json}:/app/auth.json:ro`)**:
   Mounts the authorization keys file so `CodexChatModel` can connect to `https://chatgpt.com/backend-api/codex/responses`.

---

## 3. MCP Configurations (`mcp_config.json`)

External Model Context Protocol (MCP) servers are configured inside `mcp_config.json`:
- **Path**: `/home/rutvej/Desktop/DAA/app/python-agent/src/mcp_config.py` (or workspace root `mcp_config.json`).
- **Structure**:
  ```json
  {
    "mcpServers": {
      "github-mcp": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token-here"
        }
      }
    }
  }
  ```
- **CLI Commands**: The DAA CLI provides `daa mcp list`, `daa mcp add --name <name> --cmd <command>`, and `daa mcp remove --name <name>` to modify this config file dynamically.

---

## 4. Environment Configuration
- `DAA_AGENT_MODE`: Set to `"fast"` (enables local file prompt caching and trims tool lists) or `"full"` (enables 4-dimension tools and full verification loops).
- `DAA_MAX_ITERATIONS` (default: 10): Ceil limit for agent ReAct execution thoughts.
- `DAA_MAX_TOOL_CALLS` (default: 8): Hard tool ceiling to protect against recursive call storms.
