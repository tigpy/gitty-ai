# GITTY-AI

> **AI-Powered Code Intelligence & Cybersecurity Platform**  
> *Deterministic AST parsing, property graph dependency mapping, vector semantic search, and real-time vulnerability detection.*

---

## Overview

**GITTY-AI** is a code intelligence platform that bridges source code structure, dependency graphs, and cybersecurity analysis. Rather than treating code merely as flat text chunks within an LLM context window, GITTY-AI constructs a typed property knowledge graph of the codebase (`Files`, `Classes`, `Functions`, `Imports`, `Calls`, and `Security Findings`) and couples it with dense vector embeddings for accurate semantic code retrieval and AI-assisted chat.

### Core Capabilities

- **Secure Ingestion Pipeline**: Shallow cloning (`--depth=1`) with SSRF filtering, command flag defense (`--`), symlink disabling (`core.symlinks=false`), and execution timeouts.
- **AST & Dependency Graph**: Extracts code entities, function definitions, class hierarchies, and call relationships into SQLite or Neo4j.
- **Vulnerability Intelligence**: Live query integration with the **Google OSV (Open Source Vulnerabilities)** database, complemented by static detection for hardcoded secrets and hazardous APIs (`eval`, `exec`, `shell=True`).
- **Semantic Vector Search & RAG**: 384-dimensional dense code embeddings indexed in Qdrant with real cosine similarity score propagation and SQLite embedding caching.
- **Prompt Injection Hardening**: XML boundary fencing (`<repository_untrusted_context>`) and security system prompts preventing repository code comments from hijacking LLM reasoning.
- **Full-Stack Authentication**: Native RFC 7519 HMAC-SHA256 JWT tokens and PBKDF2-HMAC-SHA256 password hashing (600,000 iterations) with strict per-user IDOR data isolation.
- **Modern Interactive UI**: React 19 + TypeScript + Vite SPA featuring interactive graph canvas, live Server-Sent Events (SSE) log terminal, and AI chat assistant with clickable symbol citations.

---

## System Architecture

```
+-------------------------------------------------------------+
|                      CLIENT LAYER                           |
|             React 19 + Vite + Lucide SPA                    |
|       (Interactive Graph, Live SSE Logs, Chat Assistant)    |
+------------------------------+------------------------------+
                               | HTTPS / SSE (with Bearer JWT)
+------------------------------v------------------------------+
|                    FASTAPI API GATEWAY                      |
|  - RFC 7519 JWT Auth & PBKDF2 Password Hashing              |
|  - IDOR-Protected Resource Ownership Checks                 |
|  - REST Endpoints (/repositories, /graph, /chat, /search)   |
|  - Async Redis SSE Progress Streaming                       |
+------------------------------+------------------------------+
                               | Task Dispatch (AMQP)
+------------------------------v------------------------------+
|                    CELERY WORKER FABRIC                     |
|  - Git Clone (SSRF & Flag-Injection Hardened)               |
|  - AST & Symbol Extraction (Python AST)                     |
|  - Dependency Risk Detection (Google OSV API + Fallback)    |
|  - Secret Detection & Dangerous API Scanning                |
|  - Dead Code Detection (DeadCodeDetectionService)           |
|  - Graph Construction & Bulk Commit                         |
|  - Semantic Code Chunking & Embeddings                      |
+-----------+--------------------+--------------------+-------+
            |                    |                    |
+-----------v-----------++-------v--------++----------v-------+
|     GRAPH STORE       ||  VECTOR STORE  ||   CACHE & QUEUE  |
| SQLite (Zero-dep)     || Qdrant Vector  || Redis (Pub/Sub)  |
| or Neo4j (Cypher)     || (Cosine 384-d) || RabbitMQ (AMQP)  |
+-----------------------++----------------++------------------+
```

For complete architectural details, see [System Architecture](docs/architecture.md).

---

## Quickstart Guide

### Prerequisites

- **Python 3.11+** or **Python 3.13**
- **Node.js 18+** and **npm**
- **Git**
- **Docker & Docker Compose** (for infrastructure services: Redis, RabbitMQ, Qdrant)

---

### Option A: Local Development (Recommended)

#### 1. Start Infrastructure Services

Launch Redis, RabbitMQ, and Qdrant using Docker Compose:

```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d redis rabbitmq qdrant
```

#### 2. Configure Python Virtual Environment

```bash
# Create and activate virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r apps/api-gateway/requirements.txt
pip install -r apps/worker/requirements.txt
pip install -e ./libs/config -e ./libs/logging -e ./libs/exceptions -e ./libs/models -e ./libs/graph -e ./libs/ai -e ./libs/events
```

#### 3. Start the API Gateway

```bash
# Windows PowerShell:
$env:PYTHONPATH="."
python -m uvicorn app.main:app --app-dir apps/api-gateway --host 0.0.0.0 --port 8000 --reload

# Linux / macOS:
PYTHONPATH=. python -m uvicorn app.main:app --app-dir apps/api-gateway --host 0.0.0.0 --port 8000 --reload
```

The API Gateway will be live at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

#### 4. Start the Celery Worker

In a separate terminal (with virtual environment active):

```bash
# Windows PowerShell:
$env:PYTHONPATH="."
celery -A apps.worker.worker_app worker --loglevel=info -P threads

# Linux / macOS:
PYTHONPATH=. celery -A apps.worker.worker_app worker --loglevel=info
```

#### 5. Start the Frontend Client

In a separate terminal:

```bash
cd apps/frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

### Option B: Full Containerized Stack

To build and run all services (API Gateway, Celery Worker, Frontend, Redis, RabbitMQ, Qdrant) in Docker:

```bash
docker compose -f infrastructure/compose/docker-compose.dev.yml up --build
```

---

## API Reference

All protected endpoints require an `Authorization: Bearer <token>` header obtained from the auth endpoints.

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT access token | No |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Yes |
| `POST` | `/api/v1/repositories/analyze` | Queue repository cloning and analysis | Yes |
| `DELETE` | `/api/v1/repositories/{id}` | Delete repository, graph nodes, and vectors | Yes (Owner) |
| `GET` | `/api/v1/repositories/{id}/progress` | Server-Sent Events stream of live logs | Yes (Owner) |
| `GET` | `/api/v1/graph/repositories` | List repositories accessible to current user | Yes |
| `GET` | `/api/v1/graph/repositories/{id}/data` | Fetch graph nodes and edges for visualization | Yes (Owner) |
| `GET` | `/api/v1/graph/repositories/{id}/expand/{node_id}` | Expand children of a file or class node | Yes (Owner) |
| `GET` | `/api/v1/graph/nodes/{node_id}` | Retrieve node details and security findings | Yes (Owner) |
| `POST` | `/api/v1/chat/sessions` | Create a new AI chat session for a repository | Yes (Owner) |
| `GET` | `/api/v1/chat/sessions/{id}` | Retrieve chat session history | Yes (Owner) |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | Send question to AI assistant with RAG citations | Yes (Owner) |
| `POST` | `/api/v1/search/semantic` | Semantic vector search across repository code | Yes (Owner) |

---

## Security Architecture

1. **Authentication & Password Storage**:
   - Zero external binary dependencies; utilizes Python standard library `hashlib.pbkdf2_hmac` with 600,000 iterations and cryptographic 16-byte random salts.
   - RFC 7519 HMAC-SHA256 JWT tokens with configurable expiration (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
2. **Access Control & Anti-IDOR**:
   - All repository analyses and chat sessions are linked to user accounts in SQLite.
   - Fast-path verification dependencies (`require_repository_owner`, `require_session_owner`) ensure users cannot access, traverse, delete, or chat about repositories owned by other users.
3. **Repository Ingestion Hardening**:
   - URLs starting with `-` or `--` command flags are strictly rejected before calling `subprocess`.
   - Loopback (`127.0.0.1`, `localhost`), link-local metadata (`169.254.169.254`), and private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are blocked to prevent Server-Side Request Forgery (SSRF).
   - Git shallow clones execute with explicit `--` delimiters and `-c core.symlinks=false` to prevent symlink traversal attacks.
4. **Prompt Injection Defense**:
   - Code context passed to the LLM is fenced inside `<repository_untrusted_context>` tags.
   - Strict system instructions mandate treating code context strictly as inert data to be analyzed, resisting prompt injection attempts embedded inside code comments or README files.

---

## Verification & Testing

The platform includes 146 automated tests across unit, integration, and security test suites:

```bash
# Run the complete test suite
pytest -v tests/
```

### Verified Test Suites

- **Security & Scanner Tests** (`tests/test_scanner_security.py`): URL validation, SSRF blocking, argument injection defense, symlink flags.
- **Authentication & IDOR Tests** (`tests/test_auth_api.py`): Password hashing, JWT signing/expiry, duplicate handling, per-user repository and session authorization.
- **Graph Batching & Scalability Tests** (`tests/test_sqlite_batching.py`): Batch insertions (`executemany`) and chunked deletions avoiding SQLite parameter limits.
- **Worker & Ingestion Tests** (`tests/test_ingestion_worker.py`, `tests/test_vector_worker.py`): End-to-end task execution, idempotent re-indexing, and progress publishing.
- **RAG & Search Tests** (`tests/test_prompt_builder.py`, `tests/test_chat_endpoints.py`, `tests/test_search_endpoints.py`): XML boundary formatting, chunk budget management, and semantic retrieval.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
