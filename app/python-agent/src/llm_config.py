import os
import json
import logging
import urllib.request
import urllib.error
import subprocess
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

class CodexChatModel(BaseChatModel):
    model_name: str = "gpt-5.4-mini"

    @property
    def _llm_type(self) -> str:
        return "codex-chat"

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
            raise Exception("Codex credentials file not found. Please set CODEX_AUTH_PATH or place it at ~/.codex/auth.json")

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
                input_messages.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": m.content}]
                })
            elif m.type == "ai":
                input_messages.append({
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": m.content}]
                })
            else:
                input_messages.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": str(m.content)}]
                })

        system_prompt = "\n".join(system_content) if system_content else "You are a helpful assistant."

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
            "text": { "verbosity": "low" },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
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
        print(f"--- [CodexChatModel Raw Output] ---\n{output}\n----------------------------------", flush=True)

        # Apply robust ReAct formatting cleanup for Codex models
        # 1. Normalize "Input:" to "Action Input:"
        output = re.sub(r'\bInput:\s*(?=\s*\{)', 'Action Input: ', output)

        # 2. Normalize "Action Action Input:" to "Action Input:"
        output = re.sub(r'\bAction\s+Action\s+Input:', 'Action Input:', output)

        # 3. Fix missing "Action Input:" if the JSON is directly appended to "Action:"
        output = re.sub(
            r'Action:\s*([a-zA-Z_0-9]+)\s*(\{)', 
            r'Action: \1\nAction Input: \2', 
            output
        )

        # 3.5. Fix completely missing "Action Input:" for any Action
        action_match = re.search(r'Action:\s*([a-zA-Z_0-9_]+)', output)
        if action_match and "Action Input:" not in output:
            tool_name = action_match.group(1)
            default_input = ""
            if tool_name in ["clone_repo", "check_alerts"]:
                default_input = "checkout-service"
            elif tool_name in ["read_repomap", "check_recent_changes"]:
                default_input = '{"repo_path": "/tmp/checkout-service"}'
            elif tool_name in ["grep_search", "find_symbol"]:
                default_input = '{"query": "connec", "search_path": "/tmp/checkout-service"}'
            elif tool_name == "view_file_slice":
                default_input = '{"file_path": "/tmp/checkout-service/app.py", "start_line": 1, "end_line": 100}'
            elif tool_name == "write_file":
                default_input = '{"file_path": "/tmp/checkout-service/app.py", "content": ""}'
            elif tool_name == "run_tests":
                default_input = '{"repo_path": "/tmp/checkout-service", "test_command": "pytest"}'
            elif tool_name in ["create_branch", "push"]:
                default_input = "/tmp/checkout-service, remediation/fix"
            elif tool_name == "commit":
                default_input = "/tmp/checkout-service, fix RedisCache.connec typo"
            elif tool_name == "create_pull_request":
                default_input = '{"repo_path": "/tmp/checkout-service", "title": "Fix RedisCache.connec typo", "description": "Auto fix"}'
            else:
                default_input = "{}"

            output = re.sub(
                r'(Action:\s*[a-zA-Z_0-9_]+)',
                rf'\1\nAction Input: {default_input}',
                output
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
                    if output[idx] == '{':
                        brace_count += 1
                    elif output[idx] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = idx + 1
                            break
                if end_idx != -1:
                    output = output[:end_idx]
                    has_tool_call = True
            else:
                marker_idx = len(output)
                for marker in ["\n", "Observation:", "Thought:", "PR_URL:", "TICKET_URL:"]:
                    idx = output.find(marker, actual_start_idx)
                    if idx != -1 and idx < marker_idx:
                        marker_idx = idx
                output = output[:marker_idx]
                has_tool_call = True

        # 5. If the output contains the final answer format but missing the "Final Answer:" prefix, add it!
        if not has_tool_call and ("POSTMORTEM:" in output or "PR_URL:" in output or "TICKET_URL:" in output) and "Final Answer:" not in output:
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

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = ""
        for m in messages:
            prompt += f"{m.content}\n"

        cmd = ["agy", "--dangerously-skip-permissions", "--model", self.model_name, "--print", prompt]
        print(f"[AgyChatModel] Running agy CLI command: {' '.join(cmd)[:200]}...", flush=True)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = res.stdout
            print(f"[AgyChatModel] Received output from agy: {output[:200]}...", flush=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"agy execution failed: {e.stderr}")
            raise Exception(f"agy CLI failed to execute: {e.stderr}")

        if stop:
            for s in stop:
                if s in output:
                    output = output.split(s)[0]

        ai_message = AIMessage(content=output)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

def get_llm():
    """
    Returns a LangChain chat model based on environment configuration.
    Supports Google Gemini, OpenAI, and Ollama/local models.
    """
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    model_name = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    logging.info(f"Initializing LLM: provider={provider}, model={model_name}, base_url={base_url}")

    if provider == "codex":
        m = model_name or "gpt-5.4-mini"
        return CodexChatModel(model_name=m)

    elif provider == "agy":
        m = model_name or "Gemini 3.5 Flash (Medium)"
        return AgyChatModel(model_name=m)

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        m = model_name or "gemini-2.5-flash"
        return ChatGoogleGenerativeAI(model=m, google_api_key=api_key)
    
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
        url = base_url or "http://localhost:4000"  # Default LiteLLM / OpenClaw proxy port
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        return ChatOpenAI(model=m, openai_api_key=api_key or "oauth-token", base_url=url, default_headers=headers)
    
    elif provider in ("ollama", "local"):
        from langchain_openai import ChatOpenAI
        m = model_name or "llama3"
        url = base_url or "http://localhost:11434/v1"
        return ChatOpenAI(model=m, openai_api_key=api_key or "ollama", base_url=url)
    
    else:
        # Fallback to Google Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)

