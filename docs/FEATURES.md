# DAA Feature Deep-Dives

This document is automatically generated from the Python codebase to ensure accurate representation of the underlying mechanics.

## LangChain ReAct Loop (Process Job)

```text
DAA 3.0 — Three-phase: Orchestrator Pre-flight -> Agent Core (free) -> Orchestrator Post-flight

Phase 1 (Pre-flight):  Fingerprint dedup, repo cache, log hydration, context packaging.
Phase 2 (Agent Core):  Planning step + hard cap + read-only investigation + write_diff/escalation.
Phase 3 (Post-flight): Parse agent output, apply diff, create branch/PR idempotently, postmortem.

If the orchestrator modules are unavailable the function gracefully degrades
to the original DAA 2.0 single-phase flow so deployments are never broken
by an incomplete rollout of the orchestrator package.
```

## Deduplication Logic (Dispatch Investigation)

```text
Computes fingerprint, runs deduplication check, records database state, and dispatches the job.
```
