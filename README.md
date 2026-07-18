# DAA — Deduplicated Autonomous SRE Platform (v3.0)

<Badges: Docker Hub, Python 3.11+, FastAPI, LangChain, License MIT>
<Hero Graphic: ./docs/assets/daa_hero.jpg>

## 1. What is DAA?
DAA is a platform designed to provide 30-60 minute triage automation by employing SHA-256 error deduplication, sliding-window policies, and a ReAct SRE agent.

### 4-Dimension Investigation
- **Change Horizon**: Analyzes recent Git commits.
- **Infrastructure**: Reviews logs and metrics.
- **Correlated Traces**: Follows request paths.
- **Surgical Code Nav**: Employs AST-based parsing to locate lines.

## 2. 60-Second Quickstart (Prebuilt Standalone Image)
Quickly spin up the standalone image locally:

```bash
docker run -d --name daa -p 8080:8080 --env-file .env daa-standalone:latest
export DAA_BACKEND_API_URL="http://localhost:8080"
```
*(Note: Internal PORT=8080 is used within the entrypoint.sh)*

Verify health with an open-auth mode synthetic check:
```bash
daa test --app demo-service --error "ValueError: standalone test"
```

## 3. Architecture & Operational Modes

DAA supports pluggable Single-Image execution vs Distributed 6-Container Compose Clusters.

| Profile | Database | Git Provider | Queue | Use Case |
|---|---|---|---|---|
| **Stateless Serverless** | `none` | `api` | `sync` | Cloud Run / Fargate |
| **Self-Contained Edge** | `sqlite` | `api`/`local`| `sync` | Single VM / Raspberry Pi |
| **Distributed Scale-Out**| `postgres` | `local` | `rabbitmq`| Datacenter / Kubernetes Compose |

## 4. Key Features
- Zero Alert Fatigue (Deduplication & Cooldowns).
- Circuit Breakers & Context Safety System (Hard 8-call budget cap).
- Universal LLM Routing (Gemini, OpenAI, Claude, Vertex, Ollama).
- Human-in-the-Loop (HITL) Dashboard Approval & Git Forge Automation (GitHub, GitLab, Gitea, Bitbucket).

## 5. Local Setup & CLI Tool (`daa`)
Installation:
```bash
./install.sh
source ~/.bashrc # Ensure daa CLI is on PATH
daa init
```

### Essential CLI commands
See `daa --help` for full usage:
- `daa init`: Initialize the setup.
- `daa test`: Send synthetic telemetry to trigger AI triage.
- `daa status`: View system status.
- `daa logs`: Stream incident logs in real-time.
- `daa redeploy`: Redeploy the platform.

## 6. Multi-Language SDK Ecosystem

| SDK | Integration Guide |
|---|---|
| **Python** | [Python SDK](./docs/sdk/python.md) |
| **Node.js** | [Node.js SDK](./docs/sdk/nodejs.md) |
| **Go** | [Go SDK](./docs/sdk/go.md) |
| **Java** | [Java SDK](./docs/sdk/java.md) |
| **Ruby** | [Ruby SDK](./docs/sdk/ruby.md) |
| **.NET** | [.NET SDK](./docs/sdk/dotnet.md) |

## 7. Codebase Layout & Documentation Roadmap
```
DAA/
├── app/
│   ├── backend-api/
│   ├── python-agent/
│   │   └── agent_src/
│   ├── admin-panel/
│   └── daa-sdk/
├── docs/            <-- Authoritative documentation
└── specs/           <-- Migrated to docs/
```
Please refer to [`/docs/index.md`](./docs/index.md) for deep-dive tutorials, architecture specs, and matrix combinations.

## 8. Contributing & License
See [CONTRIBUTING.md](./CONTRIBUTING.md), [SECURITY.md](./SECURITY.md), and [LICENSE](./LICENSE).
