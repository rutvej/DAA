# DAA SDK UI Design specification

This document details how the SDK telemetry outputs map to visual UI displays in the Admin Panel.

## 1. Traceback Serialization for SRE Rendering

The SDK does not implement user interface views. However, the exceptions and tracebacks it captures directly define the rendering on SRE pages:

- **Log details (`LogDetailsPage.js`)**:
  - The SDK sends the complete exception traceback string inside the `content` block.
  - The Admin Panel parses this traceback to render it in a custom terminal log card.
- **Surgical Code Navigation (`FixViewerPage.js`)**:
  - The traceback format must preserve absolute file paths and line offsets.
  - The SRE operator views this file path directly on the SRE code nav panel, which correlates the traceback stack frames to repository files.

---

## 2. Developer Console Logging

When an exception is captured by the Python SDK, it prints the equivalent cURL transaction to stdout to allow microservice developers to debug network connectivity:

```python
curl_command = f"curl -X POST '{self.backend_url}/logs/' -H 'Authorization: Bearer {self.token}' -H 'Content-Type: application/json' -d '{json.dumps(log)}'"
print(f"Executing equivalent curl command:\n{curl_command}")
```

This console log is captured by container monitoring agents (such as Promtail, Fluentd, or Docker Log drivers) and displayed within the SRE application logs view.
