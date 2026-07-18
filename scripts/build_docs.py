#!/usr/bin/env python3
import os
import sys
import ast

# Add the root directory to sys.path so we can import from generate_matrix
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    import generate_matrix
except ImportError:
    print(
        "Could not import generate_matrix. Please run this script from the root directory."
    )
    sys.exit(1)


def generate_index_html():
    dbs = generate_matrix.dbs
    queues = generate_matrix.queues
    gits = generate_matrix.gits

    # Generate HTML options for DBs
    db_options = "\n".join(
        [
            f'                        <option value="{db}">{db.capitalize()}</option>'
            for db in dbs
        ]
    )

    # Generate HTML options for Queues
    queue_options = "\n".join(
        [
            f'                        <option value="{q}">{q.capitalize()}</option>'
            for q in queues
        ]
    )

    # Generate HTML options for Git Mode
    git_options = "\n".join(
        [
            f'                        <option value="{g}">{g.capitalize()}</option>'
            for g in gits
        ]
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DAA — Autonomous SRE Platform</title>
    <meta name="description" content="DAA is an open-source autonomous SRE platform that triages and fixes production microservice incidents using AI.">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

    <style>
        :root {{
            --bg-base: #09090b;
            --bg-surface: #18181b;
            --bg-glass: rgba(24, 24, 27, 0.6);
            --border-light: rgba(255, 255, 255, 0.1);
            --brand-primary: #6366f1;
            --brand-primary-glow: rgba(99, 102, 241, 0.3);
            --brand-secondary: #06b6d4;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            line-height: 1.6;
            background-image: radial-gradient(circle at 15% 50%, var(--brand-primary-glow), transparent 25%),
                              radial-gradient(circle at 85% 30%, rgba(6, 182, 212, 0.15), transparent 25%);
            background-attachment: fixed;
        }}
        nav {{
            position: fixed; top: 0; width: 100%;
            background: var(--bg-glass); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-light);
            z-index: 100; display: flex; justify-content: space-between;
            align-items: center; padding: 1rem 5%;
        }}
        nav .logo {{ font-weight: 700; font-size: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }}
        nav .logo i {{ color: var(--brand-primary); }}
        nav ul {{ display: flex; gap: 2rem; list-style: none; }}
        nav a {{ color: var(--text-secondary); text-decoration: none; font-weight: 500; transition: color 0.3s; }}
        nav a:hover {{ color: var(--text-primary); }}
        .hero {{ padding: 10rem 5% 5rem; text-align: center; max-width: 900px; margin: 0 auto; }}
        .hero h1 {{ font-size: 4rem; line-height: 1.1; font-weight: 700; margin-bottom: 1.5rem; background: linear-gradient(135deg, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .hero p {{ font-size: 1.25rem; color: var(--text-secondary); margin-bottom: 2.5rem; }}
        .btn-primary {{ background: linear-gradient(135deg, var(--brand-primary), #818cf8); color: white; padding: 0.75rem 2rem; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem; }}
        .configurator-section {{ padding: 5rem 5%; max-width: 1200px; margin: 0 auto; }}
        .glass-panel {{ background: var(--bg-surface); border: 1px solid var(--border-light); border-radius: 16px; padding: 2rem; display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }}
        .controls {{ display: flex; flex-direction: column; gap: 1.5rem; }}
        .control-group label {{ display: block; font-weight: 500; margin-bottom: 0.5rem; color: var(--text-secondary); }}
        .control-group select {{ width: 100%; padding: 0.75rem 1rem; background: var(--bg-base); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: 8px; font-family: 'Inter', sans-serif; appearance: none; }}
        .code-window {{ background: #000; border-radius: 12px; border: 1px solid var(--border-light); overflow: hidden; display: flex; flex-direction: column; }}
        .code-header {{ background: #111; padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; }}
        pre {{ padding: 1.5rem; font-family: 'JetBrains Mono', monospace; font-size: 0.875rem; color: #a5b4fc; overflow-x: auto; white-space: pre-wrap; }}
        @media (max-width: 768px) {{ .glass-panel {{ grid-template-columns: 1fr; }} .hero h1 {{ font-size: 2.5rem; }} }}
    </style>
</head>
<body>
    <nav>
        <div class="logo"><i class="fa-solid fa-microchip"></i> DAA</div>
        <ul>
            <li><a href="#quickstart">Quickstart</a></li>
            <li><a href="docs/">API Docs</a></li>
            <li><a href="https://github.com/rutvej/DAA">GitHub</a></li>
        </ul>
    </nav>

    <section class="hero">
        <h1>Stop waking up at 3AM.</h1>
        <p>The open-source Autonomous SRE Platform. DAA ingests production exceptions, diagnoses the root cause, and auto-fixes it.</p>
        <a href="#quickstart" class="btn-primary"><i class="fa-solid fa-rocket"></i> Get Started</a>
    </section>

    <section id="quickstart" class="configurator-section">
        <div class="glass-panel">
            <div class="controls">
                <div class="control-group">
                    <label>Database Provider</label>
                    <select id="db-select">
{db_options}
                    </select>
                </div>
                <div class="control-group">
                    <label>Task Queue</label>
                    <select id="queue-select">
{queue_options}
                    </select>
                </div>
                <div class="control-group">
                    <label>Git Workspace Mode</label>
                    <select id="git-select">
{git_options}
                    </select>
                </div>
            </div>
            <div class="code-window">
                <div class="code-header"><button onclick="copyCode()"><i class="fa-regular fa-copy"></i></button></div>
                <pre id="code-output"></pre>
            </div>
        </div>
    </section>

    <script>
        function updateCode() {{
            const db = document.getElementById('db-select').value;
            const queue = document.getElementById('queue-select').value;
            const git = document.getElementById('git-select').value;
            
            let code = `docker run -d --name daa \\\\\\n  -p 8000:8080 \\\\\\n`;
            code += `  -e LLM_PROVIDER=google \\\\\\n`;
            code += `  -e GEMINI_API_KEY=your_api_key \\\\\\n`;
            code += `  -e DAA_DB_PROVIDER=${{db}} \\\\\\n`;
            code += `  -e DAA_QUEUE_MODE=${{queue}} \\\\\\n`;
            code += `  -e DAA_GIT_MODE=${{git}} \\\\\\n`;
            code += `  rutvej1/daa-standalone:latest`;
            document.getElementById('code-output').textContent = code;
        }}
        document.getElementById('db-select').addEventListener('change', updateCode);
        document.getElementById('queue-select').addEventListener('change', updateCode);
        document.getElementById('git-select').addEventListener('change', updateCode);
        updateCode();
    </script>
</body>
</html>"""

    with open(os.path.join(os.path.dirname(__file__), "..", "index.html"), "w") as f:
        f.write(html_content)
    print("Successfully generated index.html directly from python configuration lists.")


def generate_serverless_guide():
    # Variables pulled from Python config models (generate_matrix)
    dbs = generate_matrix.dbs
    gits = generate_matrix.gits

    serverless_db = "none" if "none" in dbs else dbs[0]
    serverless_git = "api" if "api" in gits else gits[0]

    content = f"""# Serverless Deployment Guide

This guide covers how to deploy DAA in a stateless, serverless environment such as Google Cloud Run or AWS Fargate.

## Environment Variables

For stateless mode, you MUST use the following configuration:

- `DAA_DB_PROVIDER={serverless_db}`: Disables database persistence, allowing the container to scale to zero.
- `DAA_GIT_MODE={serverless_git}`: Interacts with Git purely via the API, avoiding the need for a local clone on a persistent disk.

### Example Run Command

```bash
docker run -d --name daa \\
  -p 8000:8080 \\
  -e LLM_PROVIDER=google \\
  -e GEMINI_API_KEY=your_api_key \\
  -e DAA_DB_PROVIDER={serverless_db} \\
  -e DAA_GIT_MODE={serverless_git} \\
  -e DAA_QUEUE_MODE=sync \\
  -e DAA_AUTH_ENABLED=false \\
  -e DAA_POLICY_ENABLED=false \\
  rutvej1/daa-standalone:latest
```

When running in this mode, DAA processes incidents instantly in memory and does not require any external infrastructure like PostgreSQL or RabbitMQ.
"""
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)

    with open(os.path.join(docs_dir, "SERVERLESS_GUIDE.md"), "w") as f:
        f.write(content)
    print("Successfully generated docs/SERVERLESS_GUIDE.md")


def generate_fullstack_guide():
    dbs = generate_matrix.dbs
    queues = generate_matrix.queues
    gits = generate_matrix.gits

    fs_db = "postgres" if "postgres" in dbs else dbs[-1]
    fs_queue = "rabbitmq" if "rabbitmq" in queues else queues[-1]
    fs_git = "local" if "local" in gits else gits[-1]

    content = f"""# Full-Stack Enterprise Deployment Guide

This guide covers how to deploy DAA in a high-concurrency, distributed environment using Docker Compose.

## Architecture & Configuration

For full-stack mode (Postgres + RabbitMQ), use the following settings:

- `DAA_DB_PROVIDER={fs_db}`: Enables persistent storage using PostgreSQL.
- `DAA_QUEUE_MODE={fs_queue}`: Enables distributed task processing.
- `DAA_GIT_MODE={fs_git}`: Clones the repository locally for faster operations and deep AST analysis.

### Docker Compose Snippet

The `docker-compose.yml` should align with the connection strings required by these configurations:

```yaml
version: '3.8'
services:
  daa-api:
    image: rutvej1/daa-standalone:latest
    environment:
      - DAA_DB_PROVIDER={fs_db}
      - DAA_QUEUE_MODE={fs_queue}
      - DAA_GIT_MODE={fs_git}
      - DATABASE_URL=postgresql://user:pass@postgres:5432/daa
      - CELERY_BROKER_URL=amqp://user:pass@rabbitmq:5672/
    depends_on:
      - postgres
      - rabbitmq

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=daa

  rabbitmq:
    image: rabbitmq:3-management-alpine
```
"""
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)

    with open(os.path.join(docs_dir, "FULLSTACK_GUIDE.md"), "w") as f:
        f.write(content)
    print("Successfully generated docs/FULLSTACK_GUIDE.md")


def extract_docstring(filepath, func_name):
    if not os.path.exists(filepath):
        return "Docstring not found (file missing)."
    with open(filepath, "r") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == func_name:
                return ast.get_docstring(node) or "No docstring provided."
    return "Docstring not found."


def generate_features_md():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    ingest_path = os.path.join(
        base_dir, "app", "backend-api", "src", "routers", "ingest.py"
    )
    main_path = os.path.join(base_dir, "app", "python-agent", "agent_src", "main.py")

    dedup_doc = extract_docstring(ingest_path, "dispatch_investigation")
    react_doc = extract_docstring(main_path, "process_job")

    content = f"""# DAA Feature Deep-Dives

This document is automatically generated from the Python codebase to ensure accurate representation of the underlying mechanics.

## LangChain ReAct Loop (Process Job)

```text
{react_doc}
```

## Deduplication Logic (Dispatch Investigation)

```text
{dedup_doc}
```
"""
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "FEATURES.md"), "w") as f:
        f.write(content)
    print("Successfully generated docs/FEATURES.md")


if __name__ == "__main__":
    generate_index_html()
    generate_serverless_guide()
    generate_fullstack_guide()
    generate_features_md()
