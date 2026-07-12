# Python Agent Data Model Specification

This document details the local Pydantic data schemas, repository caching directory models, and local LLM caching structures used by the Python Agent.

## 1. Local Pydantic Model (`Job`)

The Agent consumes messages validated by the `Job` class defined in [models.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/models.py). It models the schema of incoming SRE remediation requests:

- **Attributes**:
  - `id` (str): Unique UUID of the job.
  - `log_id` (str): Foreign key to the exception log record in the backend.
  - `incident_id` (str): Foreign key to the corresponding incident.
  - `fingerprint` (str): The SHA-256 deduplication fingerprint.
  - `app_name` (str): Name of the target microservice.
  - `status` (str): Status of the queue process (e.g. `"pending"`).
  - `created_at` (str): ISO-8601 creation timestamp.
  - `updated_at` (str): ISO-8601 update timestamp.
  - `error_log` (dict): Nested dictionary holding detailed exception data (content, stack trace, trace_id, timestamp).
  - `error_file` (str, Optional): Filename identified in traceback.

---

## 2. Disk Repository Cache Model (`RepoCacheManager`)

To avoid performing full repository clones and checkout operations for every incident (which degrades performance and disk I/O), the `RepoCacheManager` implements a structured cache model:

- **Cache Root Path**: `/var/daa/repo-cache/`
- **Primary Clone**: `/var/daa/repo-cache/<app_name>/`
  - Acts as a local bare-mirror repository.
- **Sync Lock (`.daa_last_fetch`)**: `/var/daa/repo-cache/<app_name>/.daa_last_fetch`
  - Text file storing the unix timestamp of the last git fetch execution.
  - If `current_time - last_fetch < 300 seconds`, local fetch commands are bypassed (Cache TTL throttling).
- **Incident Worktrees**: `/tmp/daa/<incident_id>/`
  - Created dynamically using `git worktree add --force <path> main` pointing to the primary clone. This provides the agent with a completely isolated file system workspace for editing code and running tests.
  - Removed immediately during the post-flight phase.

---

## 3. LLM Request Cache Layout (`AgyChatModel`)

When the platform is run in fast mode (`DAA_AGENT_MODE=fast`), the `AgyChatModel` in [llm_config.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/llm_config.py#L222-L281) caches outgoing LLM completions on disk:

- **Cache Folder**: `/tmp/daa_agy_cache/`
- **Cache File**: `/tmp/daa_agy_cache/{prompt_hash}.txt`
  - The `prompt_hash` is the first 16 characters of the SHA-256 hash of the complete concatenated system prompt, tool schemas, and conversation history.
  - Subsequent requests matching the hash load the cached response instantly, avoiding external API round-trips and LLM token costs during integration tests.
