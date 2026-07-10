# Python Agent UI Design Integrations

This document details how the Python Agent formats logs and outputs for rendering in the Admin Panel web interface.

## 1. Live SRE Log Streams (`ExecutionLogCallbackHandler`)

To provide real-time SRE visibility into the agent's autonomous investigation steps, [main.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/main.py#L234-L270) registers a custom LangChain Callback Handler:

```python
class ExecutionLogCallbackHandler(BaseCallbackHandler):
    ...
```

### Formatting Contracts for React UI
The callback handler interceptor formats LangChain agent execution events into custom Markdown blocks:

- **Agent Decision Steps (`on_agent_action`)**:
  Formats thoughts and tool invocations:
  ```markdown
  🤖 **Thought:** <llm_reasoning_text>
  🛠️ **Action:** `<tool_name>` with input:
  ```json
  <tool_arguments_json>
  ```
  ```
- **Tool Observation (`on_tool_end`)**:
  Formats returned tool outputs:
  ```markdown
  👁️ **Observation:**
  ```
  <tool_output_text>
  ```
  ```
- **Agent Completion (`on_agent_finish`)**:
  ```markdown
  🏁 **Finished Investigation:** <agent_final_conclusions>
  ```

### Transmission Protocol
The callback handler transmits these blocks to the backend by executing a `POST` request to `{backend_url}/fixes/{log_id}/append-log` on every event. The React UI polls/sockets this log stream to render real-time interactive terminal logs.

---

## 2. Secrets Scrubbing

To prevent sensitive developer credentials, API tokens, database passwords, or auth header parameters from leaking into the Admin Panel logs:
- The agent passes all tool inputs and outputs through the `scrub_secrets()` function in [main.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/main.py#L114-L122).
- Key patterns (e.g. `api_key`, `secret`, `password`, `Bearer <token>`) are replaced with `***SCRUBBED***` prior to database persistence and UI distribution.

---

## 3. Postmortem Markdown Rendering

The agent's output is structured with standard Markdown headers:
- `# DAA 3.0 Postmortem`
- `## Summary`
- `## 4-Dimension Root Cause Analysis`
- `## Remediation Action Taken`
- `## Verification & Test Results`
- `## Prevention Steps`

This structured Markdown is saved in the incident's `postmortem_md` column. The Admin Panel's `FixViewerPage.js` reads this field and uses a Markdown parser to display it.
