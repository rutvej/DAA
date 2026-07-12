# Python Agent API & Tool Contract Specification

This document details the incoming queue message models and the schemas of the ReAct tools used by the Python Agent.

## 1. Incoming Queue Message Payload (`Job`)

The consumer in [main.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/main.py) reads messages from RabbitMQ. The message MUST match the following JSON schema:

```json
{
  "id": "job-uuid-111",
  "log_id": "log-uuid-222",
  "incident_id": "incident-uuid-333",
  "fingerprint": "8d3e2a0f1b",
  "trace_id": "otlp-trace-123",
  "app_name": "checkout-service",
  "status": "pending",
  "created_at": "2026-07-10T19:00:00Z",
  "updated_at": "2026-07-10T19:00:00Z",
  "error_log": {
    "id": "log-uuid-222",
    "app_name": "checkout-service",
    "content": "RedisTimeoutError: Connection timed out connecting to redis-master:6379...",
    "stack_trace": "RedisTimeoutError: Connection timed out connecting to redis-master:6379...",
    "exception_type": "RedisTimeoutError",
    "trace_id": "otlp-trace-123",
    "timestamp": "2026-07-10T19:00:00Z"
  }
}
```

---

## 2. ReAct Tools Schemas & Call Contracts

The agent has access to a set of Python functions wrapped as LangChain `Tool` instances. The LLM must generate arguments that match their input contracts:

### Code Navigation Tools
- `read_repomap`
  - **Input**: `{"repo_path": "/tmp/daa/<incident_id>"}`
  - **Output**: Markdown string representing the folder structure and file names.
- `grep_search`
  - **Input**: `{"query": "regex_or_string", "search_path": "/tmp/daa/<incident_id>"}`
  - **Output**: Matching lines with file paths and line numbers.
- `view_file_slice`
  - **Input**: `{"file_path": "/tmp/daa/<incident_id>/app/cache.py", "start_line": 1, "end_line": 100}`
  - **Output**: Lines 1-100 of the specified file.
- `find_symbol`
  - **Input**: `{"query": "ClassNameOrFunctionName", "search_path": "/tmp/daa/<incident_id>"}`
  - **Output**: File path where the symbol is defined.

### Verification Tools
- `run_tests`
  - **Input**: `{"repo_path": "/tmp/daa/<incident_id>", "test_command": "pytest"}`
  - **Output**: stdout and stderr of the test runner execution.

### Log & Alert Tools
- `query_correlated_logs`
  - **Input**: `{"query": "error", "app_name": "checkout-service", "timeframe": "120"}`
  - **Output**: Related exception trace IDs and server logs within the timeframe.
- `check_alerts`
  - **Input**: `app_name` (raw string)
  - **Output**: Active infrastructure alert descriptions.

---

## 3. MCP (Model Context Protocol) Server Contracts

The agent queries `mcp_config.json` at startup:
- It establishes a JSON-RPC session over `stdin`/`stdout` pipes with each configured MCP server command.
- Queries `tools/list` to retrieve external tool definitions.
- Registers them dynamically with the LangChain agent using the name prefix `mcp_<server_name>_<tool_name>`.
- Calls these tools by dispatching `tools/call` requests with the parameters provided by the LLM.
