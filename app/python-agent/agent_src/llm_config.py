import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class CodexChatModel(BaseChatModel):
    model_name: str = "gpt-5.4-mini"

    @property
    def _llm_type(self) -> str:
        return "codex-chat"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (urllib.error.HTTPError, urllib.error.URLError, Exception)
        ),
        reraise=True,
    )
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Load auth
        auth_path = os.environ.get("CODEX_AUTH_PATH", "/app/auth.json")
        if not os.path.exists(auth_path):
            auth_path = os.path.expanduser("~/.codex/auth.json")
        if not os.path.exists(auth_path):
            auth_path = "/etc/codex/auth.json"
        if not os.path.exists(auth_path):
            # Safe fallback default for development
            auth_path = "/home/rutvej/snap/codex/34/auth.json"

        if not os.path.exists(auth_path):
            raise Exception(
                "Codex credentials file not found. Please set CODEX_AUTH_PATH or place it at ~/.codex/auth.json"
            )

        try:
            with open(auth_path, "r") as f:
                auth_data = json.load(f)
            tokens = auth_data["tokens"]
            access_token = tokens["access_token"]
            account_id = tokens["account_id"]
        except Exception as e:
            raise Exception(f"Failed to parse Codex credentials: {e}")

        # Format prompt
        system_content = []
        input_messages = []
        for m in messages:
            if m.type == "system":
                system_content.append(m.content)
            elif m.type == "human":
                input_messages.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": m.content}],
                    }
                )
            elif m.type == "ai":
                input_messages.append(
                    {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": m.content}],
                    }
                )
            else:
                input_messages.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": str(m.content)}],
                    }
                )

        system_prompt = (
            "\n".join(system_content)
            if system_content
            else "You are a helpful assistant."
        )

        # Send request
        url = "https://chatgpt.com/backend-api/codex/responses"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "chatgpt-account-id": account_id,
            "OpenAI-Beta": "responses=experimental",
            "accept": "text/event-stream",
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }

        data = {
            "model": self.model_name,
            "store": False,
            "stream": True,
            "instructions": system_prompt,
            "input": input_messages,
            "text": {"verbosity": "low"},
        }

        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
        )

        full_text = []
        try:
            with urllib.request.urlopen(req) as response:
                for line in response:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data:"):
                        data_str = line_str[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("type") == "response.output_text.delta":
                                delta = chunk.get("delta", "")
                                full_text.append(delta)
                        except Exception:
                            pass
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            logging.error(f"Codex API HTTP error {e.code}: {err_body}")
            raise Exception(f"Codex API HTTP error {e.code}: {err_body}")
        except Exception as e:
            logging.error(f"Codex API query failed: {e}")
            raise Exception(f"Codex API query failed: {e}")

        import re

        output = "".join(full_text)
        print(
            f"--- [CodexChatModel Raw Output] ---\n{output}\n----------------------------------",
            flush=True,
        )

        # Apply robust ReAct formatting cleanup for Codex models
        # 1. Normalize "Input:" to "Action Input:"
        output = re.sub(r"\bInput:\s*(?=\s*\{)", "Action Input: ", output)

        # 2. Normalize "Action Action Input:" to "Action Input:"
        output = re.sub(r"\bAction\s+Action\s+Input:", "Action Input:", output)

        # 3. Fix missing "Action Input:" if the JSON is directly appended to "Action:"
        output = re.sub(
            r"Action:\s*([a-zA-Z_0-9]+)\s*(\{)", r"Action: \1\nAction Input: \2", output
        )

        # 3.5. Fix completely missing "Action Input:" for any Action
        action_match = re.search(r"Action:\s*([a-zA-Z_0-9_]+)", output)
        if action_match and "Action Input:" not in output:
            output = re.sub(
                r"(Action:\s*[a-zA-Z_0-9_]+)", r"\1\nAction Input: {}", output
            )

        # 4. Discard everything after the first Action Input to isolate a single tool execution
        has_tool_call = False
        action_input_idx = output.find("Action Input:")
        if action_input_idx != -1:
            start_content_idx = action_input_idx + len("Action Input:")
            content_left = output[start_content_idx:].lstrip()
            actual_start_idx = len(output) - len(content_left)

            if content_left.startswith("{"):
                brace_count = 0
                end_idx = -1
                for idx in range(actual_start_idx, len(output)):
                    if output[idx] == "{":
                        brace_count += 1
                    elif output[idx] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = idx + 1
                            break
                if end_idx != -1:
                    output = output[:end_idx]
                    has_tool_call = True
            else:
                marker_idx = len(output)
                for marker in [
                    "\n",
                    "Observation:",
                    "Thought:",
                    "PR_URL:",
                    "TICKET_URL:",
                ]:
                    idx = output.find(marker, actual_start_idx)
                    if idx != -1 and idx < marker_idx:
                        marker_idx = idx
                output = output[:marker_idx]
                has_tool_call = True

        # 5. If the output contains the final answer format but missing the "Final Answer:" prefix, add it!
        if (
            not has_tool_call
            and (
                "POSTMORTEM:" in output
                or "PR_URL:" in output
                or "TICKET_URL:" in output
            )
            and "Final Answer:" not in output
        ):
            earliest_idx = len(output)
            for marker in ["PR_URL:", "TICKET_URL:", "POSTMORTEM:"]:
                idx = output.find(marker)
                if idx != -1 and idx < earliest_idx:
                    earliest_idx = idx

            output = output[:earliest_idx] + "Final Answer:\n" + output[earliest_idx:]

        if stop:
            for s in stop:
                if s in output:
                    output = output.split(s)[0]

        ai_message = AIMessage(content=output)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])


class AgyChatModel(BaseChatModel):
    model_name: str = "Gemini 3.5 Flash (Medium)"

    @property
    def _llm_type(self) -> str:
        return "agy-chat"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((subprocess.CalledProcessError, Exception)),
        reraise=True,
    )
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import hashlib
        import pathlib

        prompt = ""
        for m in messages:
            prompt += f"{m.content}\n"

        agent_mode = os.environ.get("DAA_AGENT_MODE", "full")
        cache_hit = False
        cache_file = None

        if agent_mode == "fast":
            cache_dir = pathlib.Path("/tmp/daa_agy_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
            cache_file = cache_dir / f"{prompt_hash}.txt"
            if cache_file.exists():
                print(f"[AgyChatModel] Cache HIT for hash {prompt_hash}", flush=True)
                output = cache_file.read_text(encoding="utf-8")
                cache_hit = True

        if not cache_hit:
            cmd = [
                "agy",
                "--dangerously-skip-permissions",
                "--model",
                self.model_name,
                "--print",
                prompt,
            ]
            print(
                f"[AgyChatModel] Running agy CLI command: {' '.join(cmd)[:200]}...",
                flush=True,
            )
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = res.stdout
                print(
                    f"[AgyChatModel] Received output from agy: {output[:200]}...",
                    flush=True,
                )
            except subprocess.CalledProcessError as e:
                logging.error(f"agy execution failed: {e.stderr}")
                raise Exception(f"agy CLI failed to execute: {e.stderr}")

            if agent_mode == "fast" and cache_file:
                try:
                    cache_file.write_text(output, encoding="utf-8")
                    print(f"[AgyChatModel] Cached response to {cache_file}", flush=True)
                except Exception as ce:
                    print(f"[AgyChatModel] Failed to write cache: {ce}", flush=True)

        if stop:
            for s in stop:
                if s in output:
                    output = output.split(s)[0]

        ai_message = AIMessage(content=output)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])


class MockChatModel(BaseChatModel):
    model_name: str = "mock-model"
    _call_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        object.__setattr__(self, "_call_count", self._call_count + 1)
        policy_on = os.environ.get("DAA_POLICY_ENABLED", "false").lower() == "true"
        if self._call_count == 1:
            # Step 1: read a file so the orchestrator sees real investigation activity
            output = (
                "Thought: Let me look at the main application file to understand the error.\n"
                "Action: read_file\n"
                "Action Input: requirements.txt"
            )
        else:
            # Step 2: output the structured DAA 3.0 terminal marker.
            # The postflight orchestrator parses WRITE_DIFF to create a branch/commit/PR
            # via CloneFreeGitClient without the agent calling any git tools directly.
            if policy_on:
                # WRITE_ESCALATION triggers the awaiting_approval policy flow.
                output = (
                    "Final Answer:\n"
                    "WRITE_ESCALATION:\n"
                    "REASON: Mock policy-gated escalation.\n"
                    "PARTIAL_DIAGNOSIS: RedisConnectionError detected in payment-api; "
                    "proposed fix requires approval before merging."
                )
            else:
                output = (
                    "Final Answer:\n"
                    "WRITE_DIFF:\n"
                    "--- a/requirements.txt\n"
                    "+++ b/requirements.txt\n"
                    "@@ -1,2 +1,3 @@\n"
                    " redis==4.5.4\n"
                    "+redis-retry==1.0.0\n"
                    " fastapi==0.103.1\n"
                    "EXPLANATION: Added redis-retry package to handle transient RedisConnectionError "
                    "in payment-api checkout endpoint."
                )

        ai_message = AIMessage(content=output)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_chat_completion(
    messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any
) -> ChatResult:
    """
    Direct chat completion wrapper with tenacity exponential backoff and circuit breaker protection.
    """
    llm = get_llm()
    return llm.invoke(messages, stop=stop, **kwargs)


def get_llm():
    """
    Returns a LangChain chat model based on environment configuration.
    Supports Google Gemini, OpenAI, and Ollama/local models.
    """
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    model_name = os.environ.get("LLM_MODEL")
    api_key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    base_url = os.environ.get("LLM_BASE_URL")

    logging.info(
        f"Initializing LLM: provider={provider}, model={model_name}, base_url={base_url}"
    )

    if provider == "mock":
        return MockChatModel()

    elif provider == "codex":
        m = model_name or "gpt-5.4-mini"
        return CodexChatModel(model_name=m)

    elif provider == "agy":
        m = model_name or "Gemini 3.5 Flash (Medium)"
        return AgyChatModel(model_name=m)

    elif provider == "google":
        import random
        import time

        from google.api_core.exceptions import ResourceExhausted
        from langchain_core.outputs import ChatResult
        from langchain_google_genai import ChatGoogleGenerativeAI

        class RateLimitedGemini(ChatGoogleGenerativeAI):
            def _generate(
                self, messages, stop=None, run_manager=None, **kwargs
            ) -> ChatResult:
                max_retries = 8
                base_delay = 2.0

                for attempt in range(max_retries):
                    try:
                        timestamp = time.time()
                        logging.info(
                            f"[RateLimitedGemini] Sending request at {timestamp}"
                        )
                        with open("/tmp/gemini_requests.log", "a") as f:
                            f.write(f"{timestamp}\n")
                        return super()._generate(
                            messages, stop=stop, run_manager=run_manager, **kwargs
                        )
                    except ResourceExhausted as e:
                        if attempt == max_retries - 1:
                            raise

                        retry_after = None
                        if hasattr(e, "response") and e.response is not None:
                            retry_after = e.response.headers.get("Retry-After")

                        if retry_after and str(retry_after).isdigit():
                            delay = float(retry_after)
                        else:
                            delay = base_delay * (2**attempt) + random.uniform(0, 1)

                        logging.warning(
                            f"[RateLimitedGemini] 429 Rate Limit Hit. Sleeping for {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})."
                        )
                        time.sleep(delay)

        import asyncio

        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        m = model_name or "gemini-2.5-flash"
        return RateLimitedGemini(model=m, google_api_key=api_key)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        m = model_name or "gpt-4o"
        return ChatOpenAI(model=m, openai_api_key=api_key, base_url=base_url)

    elif provider in ("anthropic", "claude"):
        from langchain_anthropic import ChatAnthropic

        m = model_name or "claude-3-5-sonnet-20241022"
        return ChatAnthropic(model=m, anthropic_api_key=api_key)

    elif provider in ("openclaw", "litellm", "proxy", "custom"):
        # Universal OpenAI-compatible proxy support (OpenClaw, LiteLLM, Roo, Cursor, OAuth / sign-in code bearer tokens)
        from langchain_openai import ChatOpenAI

        m = model_name or "codex"
        url = (
            base_url or "http://localhost:4000"
        )  # Default LiteLLM / OpenClaw proxy port
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        return ChatOpenAI(
            model=m,
            openai_api_key=api_key or "oauth-token",
            base_url=url,
            default_headers=headers,
        )

    elif provider in ("ollama", "local"):
        from langchain_openai import ChatOpenAI

        m = model_name or "llama3"
        url = base_url or "http://localhost:11434/v1"
        return ChatOpenAI(model=m, openai_api_key=api_key or "ollama", base_url=url)

    else:
        # Fallback to Google Gemini
        import random
        import time

        from google.api_core.exceptions import ResourceExhausted
        from langchain_core.outputs import ChatResult
        from langchain_google_genai import ChatGoogleGenerativeAI

        class RateLimitedGemini(ChatGoogleGenerativeAI):
            def _generate(
                self, messages, stop=None, run_manager=None, **kwargs
            ) -> ChatResult:
                max_retries = 8
                base_delay = 2.0

                for attempt in range(max_retries):
                    try:
                        timestamp = time.time()
                        logging.info(
                            f"[RateLimitedGemini] Sending request at {timestamp}"
                        )
                        with open("/tmp/gemini_requests.log", "a") as f:
                            f.write(f"{timestamp}\n")
                        return super()._generate(
                            messages, stop=stop, run_manager=run_manager, **kwargs
                        )
                    except ResourceExhausted as e:
                        if attempt == max_retries - 1:
                            raise

                        retry_after = None
                        if hasattr(e, "response") and e.response is not None:
                            retry_after = e.response.headers.get("Retry-After")

                        if retry_after and str(retry_after).isdigit():
                            delay = float(retry_after)
                        else:
                            delay = base_delay * (2**attempt) + random.uniform(0, 1)

                        logging.warning(
                            f"[RateLimitedGemini] 429 Rate Limit Hit. Sleeping for {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})."
                        )
                        time.sleep(delay)

        return RateLimitedGemini(model="gemini-2.5-flash", google_api_key=api_key)
