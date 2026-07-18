# DAA CLI Reference

The `daa` command-line tool provides a unified interface for managing the DAA platform, from initial setup to real-time debugging.

## Core Commands

### `daa init`
Initializes a new DAA deployment. It configures the environment variables, sets up the database, and prompts you to select a Large Language Model and deployment profile.

### `daa register`
Registers a new target application with the DAA platform to enable error ingestion and monitoring.
```bash
daa register --name <app-name> --repo <git-url> --language <language>
```

### `daa policy`
Configures the escalation threshold and window for an application.
```bash
daa policy --app <app-name> --threshold <count> --window <seconds>
```

## Operational Commands

### `daa test`
Sends a synthetic error to the backend API to trigger the triage agent. Used for verifying that the deduplication, queues, and LLM routes are functioning correctly.
```bash
daa test --app <app-name> --error "<error message>"
```

### `daa status`
Pings the health endpoint of the backend API and outputs the system status.
```bash
daa status
```

### `daa logs`
Streams the real-time processing logs from the agent. Essential for observing the AI's "thought process" and AST search steps.
```bash
daa logs [--follow]
```

### `daa redeploy`
Redeploys the platform containers or standalone instance.
```bash
daa redeploy
```

## MCP Commands

### `daa mcp list`
Lists all configured MCP servers.

### `daa mcp add`
Adds a new MCP server.

### `daa mcp remove`
Removes an MCP server by ID.

## Other Commands

### `daa config set-model`
Updates the configured LLM model without a full re-initialization.

### `daa version`
Prints the CLI version (`v3.0.0`).
