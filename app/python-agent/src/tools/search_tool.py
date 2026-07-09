import os
import sqlite3
import re
from pydantic.v1 import BaseModel, Field
from langchain_core.tools import tool

class SearchRepoInput(BaseModel):
    query: str = Field(description="The search query to find relevant code snippets (e.g. 'redis cache session key timeout')")
    repo_path: str = Field(default="/tmp/payment-api", description="The path to the cloned repository to search.")

def index_repo(repo_path: str):
    """
    Builds a local SQLite FTS5 index of the codebase at repo_path.
    Chunks files into 40-line overlapping windows.
    """
    db_path = os.path.join(repo_path, ".daa_search_index.db")
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE code_chunks USING fts5(
                file_path,
                start_line UNINDEXED,
                end_line UNINDEXED,
                content
            );
        """)
        conn.commit()
    except Exception:
        cursor.execute("""
            CREATE TABLE code_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                start_line INTEGER,
                end_line INTEGER,
                content TEXT
            );
        """)
        cursor.execute("CREATE INDEX idx_content ON code_chunks(content);")
        conn.commit()

    allowed_exts = {".py", ".go", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".rs", ".rb", ".php", ".cs", ".kt"}
    ignored_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist", "target", ".idea", ".vscode"}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in allowed_exts:
                continue
                
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, repo_path)
            
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            window_size = 40
            overlap = 10
            i = 0
            while i < len(lines):
                chunk_lines = lines[i:i + window_size]
                chunk_content = "".join(chunk_lines)
                start_line = i + 1
                end_line = i + len(chunk_lines)
                
                cursor.execute(
                    "INSERT INTO code_chunks (file_path, start_line, end_line, content) VALUES (?, ?, ?, ?)",
                    (rel_path, start_line, end_line, chunk_content)
                )
                
                i += (window_size - overlap)
                
    conn.commit()
    conn.close()

@tool(args_schema=SearchRepoInput)
def search_repo(query: str, repo_path: str = "/tmp/payment-api") -> str:
    """Queries the local codebase search index to return the top relevant code snippets.

    Args:
        query: The search terms or code query.
        repo_path: The path to the repository directory.
    """
    repo_path = repo_path.strip().strip("'\"")

    if os.environ.get("DAA_GIT_MODE") == "api":
        from .file_system_tool import parse_api_path
        app_name, relative_path = parse_api_path(repo_path)
        from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES
        client = CloneFreeGitClient(app_name)
        ref = ACTIVE_BRANCHES.get(app_name, "main")
        results = client.search_code(query, ref=ref)
        if not results:
            return "No matching code snippets found. Try different search terms."
            
        snippets = []
        for match in results[:3]:
            file_path = match.split(":")[0]
            content = client.get_file_content(file_path, ref=ref)
            if content:
                lines = content.splitlines()[:40]
                snippets.append(f"=== File: {file_path} (Lines 1-{len(lines)}) ===\n" + "\n".join(lines))
        if snippets:
            return "\n\n".join(snippets)
        return "\n".join(results)

    db_path = os.path.join(repo_path, ".daa_search_index.db")
    
    if not os.path.exists(db_path):
        try:
            index_repo(repo_path)
        except Exception as e:
            return f"Error building code search index: {e}"

    if not os.path.exists(db_path):
        return "Code search index not found and could not be initialized."

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
        if not clean_query:
            clean_query = query

        is_fts5 = False
        try:
            cursor.execute("SELECT sql FROM sqlite_master WHERE name='code_chunks';")
            sql_def = cursor.fetchone()
            if sql_def and "fts5" in sql_def[0].lower():
                is_fts5 = True
        except Exception:
            pass

        if is_fts5:
            cursor.execute(
                "SELECT file_path, start_line, end_line, content FROM code_chunks WHERE code_chunks MATCH ? LIMIT 5",
                (clean_query,)
            )
        else:
            like_pat = f"%{clean_query}%"
            cursor.execute(
                "SELECT file_path, start_line, end_line, content FROM code_chunks WHERE content LIKE ? LIMIT 5",
                (like_pat,)
            )
            
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "No matching code snippets found. Try different search terms."
            
        results = []
        for r in rows:
            file_path, start_line, end_line, content = r
            snippet = f"=== File: {file_path} (Lines {start_line}-{end_line}) ===\n{content}\n"
            results.append(snippet)
            
        return "\n".join(results)
    except Exception as e:
        return f"Error executing codebase search: {e}"
