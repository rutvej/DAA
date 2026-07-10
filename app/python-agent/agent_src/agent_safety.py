# agent_safety.py
# DAA 3.0 — Context Safety Layer
# Layer 1: Planning Step (agent must declare plan as JSON before calling tools)
# Layer 2: Hard cap at 8 tool calls with warning injection at 5

import json
import logging
import re
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CapExceededException(Exception):
    """Raised by HardCapCallbackHandler when the tool-call budget is exhausted."""
    pass


# ---------------------------------------------------------------------------
# Layer 1 — Planning Validator
# ---------------------------------------------------------------------------

class PlanningValidator:
    """
    Enforces the planning step: the agent's first LLM output must be a
    structured JSON investigation plan before it may invoke any tools.

    This prevents agents from jumping straight into tool calls without
    reasoning about what evidence they actually need.
    """

    # JSON block pattern: matches ```json ... ``` fences OR a bare {...} block
    _JSON_FENCE_RE = re.compile(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        re.DOTALL,
    )
    _BARE_JSON_RE = re.compile(r"(\{.*\})", re.DOTALL)

    REQUIRED_KEYS = {"hypothesis", "evidence_needed", "will_not_check"}

    def __init__(self) -> None:
        pass

    def extract_plan(self, llm_output: str) -> Optional[Dict]:
        """
        Try to extract a valid investigation plan JSON from the first LLM output.

        Accepts both fenced (```json ... ```) and bare ``{ ... }`` blocks.
        The JSON must contain all three required keys:
            - ``hypothesis``       : root-cause hypothesis string
            - ``evidence_needed``  : list of evidence dicts
            - ``will_not_check``   : list of deliberately skipped items

        Args:
            llm_output: Raw text of the agent's first response.

        Returns:
            Parsed plan dict, or None if no valid plan was found.
        """
        # Prefer a fenced JSON block
        match = self._JSON_FENCE_RE.search(llm_output)
        if not match:
            match = self._BARE_JSON_RE.search(llm_output)
        if not match:
            logger.debug("No JSON block found in first LLM output")
            return None

        raw_json = match.group(1)
        try:
            plan = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning("Plan JSON decode error: %s", exc)
            return None

        if not isinstance(plan, dict):
            return None

        missing = self.REQUIRED_KEYS - plan.keys()
        if missing:
            logger.warning("Plan missing required keys: %s", missing)
            return None

        return plan

    def format_plan_prompt(self) -> str:
        """
        Return the instruction block to prepend to the agent's system prompt.

        This tells the agent it MUST emit a structured plan before using tools.
        """
        return (
            "IMPORTANT: Your FIRST output must be a JSON investigation plan "
            "in this exact format:\n"
            "{{\n"
            '  "hypothesis": "<your hypothesis about the root cause>",\n'
            '  "evidence_needed": [\n'
            '    {{"type": "file"|"metrics"|"logs"|"git", '
            '"target": "<file path or signal name>", '
            '"reason": "<why>"}}\n'
            "  ],\n"
            '  "will_not_check": ["<things you will deliberately not investigate>"]\n'
            "}}\n"
            "Only after submitting this plan may you call investigation tools."
        )


# ---------------------------------------------------------------------------
# Layer 2 — Hard Cap Callback Handler
# ---------------------------------------------------------------------------

class HardCapCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that enforces a hard ceiling on tool calls.

    Behaviour:
    - Counts every ``on_tool_start`` invocation.
    - At *warning_at* calls: sets a warning flag so the next agent step can
      inject a budget-warning message into the conversation.
    - At *max_calls* calls: raises ``CapExceededException`` to abort the
      agent loop immediately.

    Usage:
        handler = HardCapCallbackHandler(max_calls=8, warning_at=5)
        agent_executor.invoke(..., config={"callbacks": [handler]})
    """

    def __init__(self, max_calls: int = 8, warning_at: int = 5) -> None:
        super().__init__()
        if warning_at >= max_calls:
            raise ValueError("warning_at must be less than max_calls")
        self.max_calls = max_calls
        self.warning_at = warning_at
        self.call_count: int = 0
        self._warning_triggered: bool = False

    # ------------------------------------------------------------------
    # LangChain callback hooks
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """
        Called by LangChain immediately before a tool is invoked.

        Increments the call counter, sets the warning flag at *warning_at*,
        and raises ``CapExceededException`` at *max_calls*.
        """
        self.call_count += 1
        tool_name = (serialized or {}).get("name", "<unknown>")
        logger.debug(
            "Tool call #%d/%d: %s", self.call_count, self.max_calls, tool_name
        )

        if self.call_count == self.warning_at:
            self._warning_triggered = True
            logger.warning(
                "DAA safety: %d/%d tool calls used — agent approaching budget limit.",
                self.call_count,
                self.max_calls,
            )

        if self.call_count >= self.max_calls:
            logger.error(
                "DAA safety: hard cap of %d tool calls exceeded — aborting agent.",
                self.max_calls,
            )
            raise CapExceededException(
                f"Agent exceeded the tool call budget of {self.max_calls}."
            )

    # ------------------------------------------------------------------
    # Warning message injection
    # ------------------------------------------------------------------

    def get_warning_message(self) -> Optional[str]:
        """
        Return a warning string if the call count has reached *warning_at*,
        otherwise return None.

        Callers should inject this message into the next agent step's input
        so the model knows it is running low on its tool budget.
        """
        if self.call_count >= self.warning_at:
            remaining = self.max_calls - self.call_count
            return (
                f"[DAA BUDGET WARNING] You have used {self.call_count} of "
                f"{self.max_calls} allowed tool calls. "
                f"Only {remaining} call(s) remaining. "
                "Conclude your investigation and produce a fix or escalation now."
            )
        return None

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def is_warning_triggered(self) -> bool:
        """True if the warning threshold has been crossed."""
        return self._warning_triggered

    def reset(self) -> None:
        """Reset counters (useful between retries in tests)."""
        self.call_count = 0
        self._warning_triggered = False


# ---------------------------------------------------------------------------
# AgentSafetyWrapper
# ---------------------------------------------------------------------------

class AgentSafetyWrapper:
    """
    Thin wrapper around a LangChain ``AgentExecutor`` that enforces both
    safety layers in a single ``invoke()`` call.

    Layer 1 (planning) is enforced by embedding ``PlanningValidator``
    instructions into the system prompt before the first LLM call.

    Layer 2 (hard cap) is enforced by attaching a ``HardCapCallbackHandler``
    to every ``invoke()`` call.

    On cap breach, the wrapper catches ``CapExceededException`` and returns a
    structured escalation dict instead of letting the exception propagate.
    """

    def __init__(
        self,
        agent_executor: Any,
        max_calls: int = 8,
        warning_at: int = 5,
    ) -> None:
        """
        Args:
            agent_executor: A configured LangChain ``AgentExecutor`` instance.
            max_calls:      Hard ceiling on tool invocations per agent run.
            warning_at:     Tool call count at which the budget warning is set.
        """
        self.agent_executor = agent_executor
        self.max_calls = max_calls
        self.warning_at = warning_at

        # Reusable validator for plan-prompt generation
        self._planning_validator = PlanningValidator()

    def invoke(self, input_dict: dict, callbacks: list = None) -> dict:
        """
        Invoke the agent with both safety layers active.

        Args:
            input_dict: Input dict passed to ``agent_executor.invoke()``.
                        Should contain at least ``{"input": "..."}`` or
                        whatever the executor expects.
            callbacks:  Additional LangChain callbacks to attach alongside
                        the hard-cap handler.

        Returns:
            The agent executor's output dict, or on cap breach:
            {"output": "ESCALATION: Agent exceeded tool call budget.", "cap_exceeded": True}
        """
        # Instantiate a fresh handler so counts start at 0 for each run
        cap_handler = HardCapCallbackHandler(
            max_calls=self.max_calls,
            warning_at=self.warning_at,
        )

        all_callbacks = [cap_handler] + (callbacks or [])

        try:
            result = self.agent_executor.invoke(
                input_dict,
                config={"callbacks": all_callbacks},
            )
            return result

        except CapExceededException as exc:
            logger.error("AgentSafetyWrapper caught CapExceededException: %s", exc)
            return {
                "output": "ESCALATION: Agent exceeded tool call budget.",
                "cap_exceeded": True,
            }

        except Exception as exc:
            # Surface unexpected errors with context rather than silently swallowing
            logger.error("AgentSafetyWrapper unexpected error: %s", exc, exc_info=True)
            raise

    def get_plan_prompt(self) -> str:
        """
        Return the planning-step instruction string to prepend to the system
        prompt before calling ``invoke()``.
        """
        return self._planning_validator.format_plan_prompt()

    def validate_plan(self, llm_output: str) -> Optional[Dict]:
        """
        Delegate to ``PlanningValidator.extract_plan()``.

        Useful for callers that want to inspect or log the plan separately.
        """
        return self._planning_validator.extract_plan(llm_output)
