import os
import json
import ast
import re
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from .file_system_tool import get_full_path, parse_api_path


class ViewFileSliceInput(BaseModel):
    data: str = Field(
        description='A JSON string containing \'file_path\', optional \'start_line\' (1-indexed, default 1), and optional \'end_line\' (default 100). Example: {"file_path": "/app/main.py", "start_line": 10, "end_line": 50}'
    )


@tool(args_schema=ViewFileSliceInput)
def view_file_slice(data: str) -> str:
    """Reads a slice of lines from a file with line numbers prefixed. Enforces a maximum 100-line guardrail to prevent context flooding."""
    try:
        input_data = json.loads(data)
        file_path = input_data.get("file_path")
        if not file_path:
            return "Error: 'file_path' is required."
        start_line = int(input_data.get("start_line", 1))
        end_line = int(input_data.get("end_line", start_line + 99))

        if start_line < 1:
            start_line = 1
        if end_line < start_line:
            end_line = start_line

        truncated_msg = ""
        if end_line - start_line >= 100:
            end_line = start_line + 99
            truncated_msg = "\n[TRUNCATED: Maximum slice limit is 100 lines per call to prevent token flooding]"

        # Support DAA_GIT_MODE=api
        if os.environ.get("DAA_GIT_MODE") == "api":
            app_name, relative_path = parse_api_path(file_path)
            from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

            client = CloneFreeGitClient(app_name)
            ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
            content = client.get_file_content(relative_path, ref=ref)
            if content is None:
                return f"Error: File not found via API at {file_path}"
            lines = content.splitlines(keepends=True)
        else:
            full_path = get_full_path(file_path.strip())
            if not os.path.exists(full_path):
                return f"Error: File not found at {file_path}"

            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

        total_lines = len(lines)
        if start_line > total_lines:
            return f"Error: start_line ({start_line}) is greater than total lines ({total_lines}) in {file_path}"

        slice_lines = lines[start_line - 1 : end_line]
        output = []
        for idx, line in enumerate(slice_lines, start=start_line):
            output.append(f"{idx}: {line.rstrip()}")

        return "\n".join(output) + truncated_msg
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error reading file slice: {e}"


class GrepSearchInput(BaseModel):
    data: str = Field(
        description='A JSON string containing \'query\' (string to search) and optional \'search_path\' (default \'.\'). Example: {"query": "def process_payment", "search_path": "/app"}'
    )


@tool(args_schema=GrepSearchInput)
def grep_search(data: str) -> str:
    """Performs a grep-like search across files in the codebase."""
    try:
        input_data = json.loads(data)
        query = input_data.get("query")
        if not query:
            return "Error: 'query' is required."
        search_path = input_data.get("search_path", ".")

        # Support DAA_GIT_MODE=api
        if os.environ.get("DAA_GIT_MODE") == "api":
            app_name, relative_path = parse_api_path(search_path)
            from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

            client = CloneFreeGitClient(app_name)
            ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
            results = client.search_code(query, ref=ref)
            if not results:
                return f"No matches found for query: '{query}'"
            return "\n".join(results)

        full_dir = get_full_path(search_path.strip())
        if not os.path.exists(full_dir):
            return f"Error: Search directory not found: {search_path}"

        ignore_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "bin",
            "obj",
            "dist",
            "build",
        }
        matches = []
        max_matches = 50

        # Determine query patterns (supports case-insensitivity)
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except Exception:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        for root, dirs, files in os.walk(full_dir):
            dirs[:] = [
                d for d in dirs if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in files:
                if file.endswith(
                    (".pyc", ".o", ".exe", ".dll", ".so", ".png", ".jpg", ".zip")
                ):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, start=1):
                            if pattern.search(line):
                                rel_path = os.path.relpath(file_path, full_dir)
                                matches.append(f"{rel_path}:{idx}: {line.strip()}")
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

        if not matches:
            return f"No matches found for query: '{query}'"

        res = "\n".join(matches)
        if len(matches) >= max_matches:
            res += "\n[TRUNCATED: Showing first 50 matches]"
        return res
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error during grep search: {e}"


class FindSymbolInput(BaseModel):
    data: str = Field(
        description='A JSON string containing \'symbol_name\' (class, function, or struct name) and optional \'search_path\' (default \'.\'). Example: {"symbol_name": "PaymentService", "search_path": "/app"}'
    )


@tool(args_schema=FindSymbolInput)
def find_symbol(data: str) -> str:
    """Locates the definition of a class, function, method, or struct across the codebase using AST and regex analysis."""
    try:
        input_data = json.loads(data)
        symbol = input_data.get("symbol_name") or input_data.get("symbol")
        if not symbol:
            return "Error: 'symbol_name' is required."
        search_path = input_data.get("search_path", ".")

        # Support DAA_GIT_MODE=api
        if os.environ.get("DAA_GIT_MODE") == "api":
            app_name, relative_path = parse_api_path(search_path)
            from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

            client = CloneFreeGitClient(app_name)
            ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
            results = client.search_code(symbol, ref=ref)
            if not results:
                return f"Symbol '{symbol}' not found via API."
            res_str = f"Found potential matches for symbol '{symbol}':\n"
            res_str += "\n".join(results)
            return res_str

        full_dir = get_full_path(search_path.strip())
        if not os.path.exists(full_dir):
            return f"Error: Search directory not found: {search_path}"

        ignore_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "bin",
            "obj",
            "dist",
            "build",
        }
        results = []

        for root, dirs, files in os.walk(full_dir):
            dirs[:] = [
                d for d in dirs if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, full_dir)

                if file.endswith(".py"):
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                        tree = ast.parse(content, filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(
                                node,
                                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                            ):
                                if node.name == symbol:
                                    doc = ast.get_docstring(node) or "No docstring"
                                    results.append(
                                        f"File: {rel_path}\nType: {'Class' if isinstance(node, ast.ClassDef) else 'Function'}\nLine: {node.lineno}\nDocstring: {doc}\n"
                                    )
                    except Exception:
                        pass
                elif file.endswith((".go", ".js", ".ts", ".java", ".rb")):
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            for idx, line in enumerate(f, start=1):
                                stripped = line.strip()
                                if symbol in stripped and any(
                                    stripped.startswith(prefix)
                                    for prefix in [
                                        "func",
                                        "class",
                                        "function",
                                        "interface",
                                        "def",
                                        "public class",
                                    ]
                                ):
                                    results.append(
                                        f"File: {rel_path}\nMatch: {stripped}\nLine: {idx}\n"
                                    )
                    except Exception:
                        pass

        if not results:
            return f"Symbol '{symbol}' not found in {search_path}"
        return "\n".join(results)
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error finding symbol: {e}"


class ReadRepomapInput(BaseModel):
    data: str = Field(
        description="A JSON string containing optional 'repo_path' (default '.'). Example: {\"repo_path\": \"/app\"}"
    )


@tool(args_schema=ReadRepomapInput)
def read_repomap(data: str) -> str:
    """Generates a skeleton map of the repository showing key classes, functions, and files."""
    try:
        input_data = json.loads(data)
        repo_path = input_data.get("repo_path", ".")

        # Support DAA_GIT_MODE=api
        if os.environ.get("DAA_GIT_MODE") == "api":
            app_name, relative_path = parse_api_path(repo_path)
            from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

            client = CloneFreeGitClient(app_name)
            ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"

            all_files = client.list_all_files(ref=ref)
            matching_files = [
                f
                for f in all_files
                if f.endswith((".py", ".go", ".js", ".ts", ".java", ".rb"))
            ]

            skeleton_lines = []
            max_lines = 1000
            for file_path in sorted(matching_files)[:10]:
                skeleton_lines.append(f"\n=== File: {file_path} ===")
                content = client.get_file_content(file_path, ref=ref)
                if content:
                    for line in content.splitlines()[:50]:
                        stripped = line.strip()
                        if re.match(
                            r"^(class|def|func|interface|function)\s+", stripped
                        ):
                            skeleton_lines.append(f"  {stripped}")

            return "\n".join(skeleton_lines)

        full_dir = get_full_path(repo_path.strip())
        if not os.path.exists(full_dir):
            return f"Error: Repository directory not found: {repo_path}"

        ignore_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "bin",
            "obj",
            "dist",
            "build",
            "tests",
        }
        skeleton_lines = []
        max_lines = 1000

        for root, dirs, files in os.walk(full_dir):
            dirs[:] = [
                d for d in dirs if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in sorted(files):
                if not file.endswith((".py", ".go", ".js", ".ts", ".java", ".rb")):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, full_dir)

                skeleton_lines.append(f"\n=== File: {rel_path} ===")
                try:
                    if file.endswith(".py"):
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                        tree = ast.parse(content)
                        for node in tree.body:
                            if isinstance(node, ast.ClassDef):
                                skeleton_lines.append(f"class {node.name}(...):")
                                doc = ast.get_docstring(node)
                                if doc:
                                    skeleton_lines.append(
                                        f'    """{doc.splitlines()[0]}"""'
                                    )
                                for item in node.body:
                                    if isinstance(
                                        item, (ast.FunctionDef, ast.AsyncFunctionDef)
                                    ):
                                        skeleton_lines.append(
                                            f"    def {item.name}(...): ..."
                                        )
                            elif isinstance(
                                node, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                skeleton_lines.append(f"def {node.name}(...): ...")
                    else:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            for line in f:
                                stripped = line.strip()
                                if re.match(
                                    r"^(public|private|protected|export|default|func|class|interface|type|def)\s+",
                                    stripped,
                                ):
                                    skeleton_lines.append(f"  {stripped[:80]} ...")
                except Exception:
                    skeleton_lines.append("  [Error parsing file skeleton]")

                if len(skeleton_lines) >= max_lines:
                    break
            if len(skeleton_lines) >= max_lines:
                break

        res = "\n".join(skeleton_lines)
        if len(skeleton_lines) >= max_lines:
            res += "\n\n[TRUNCATED: Repomap capped at 1000 lines]"
        return res
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error generating repomap: {e}"
