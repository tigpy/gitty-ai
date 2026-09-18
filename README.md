# GITTY-AI

<div align="center">

![GITTY-AI Header](docs/assets/readme/architecture.png)

### Deterministic Code Intelligence & Cybersecurity Cockpit

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Celery](https://img.shields.io/badge/Celery-5.3+-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-DC2626?style=flat-square&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](#license)

**[Explore Cockpit](#cockpit-showcase)** • **[System Architecture](#system-architecture)** • **[How It Works](#how-it-works)** • **[Quickstart](#getting-started)** • **[Security Model](#security-architecture)** • **[Test Suite](#verification--testing)**

</div>

---

## Overview

Modern software repositories are complex, interconnected graphs of modules, classes, call hierarchies, external dependencies, and potential security vulnerabilities. Treating a codebase as flat text snippets inside an LLM context window causes hallucinations, misses transitive call relationships, and fails to diagnose architectural security flaws.

**GITTY-AI** is a code intelligence and cybersecurity platform that bridges deterministic AST parsing, property graph dependency mapping, dense vector semantic retrieval, and live vulnerability intelligence into an interactive real-time cockpit.

When a repository is ingested, GITTY-AI clones it within a hardened sandbox, constructs a typed property knowledge graph (`Repository`, `File`, `Class`, `Function`, `Import`, `Call`), identifies security vulnerabilities using the Google OSV database and static taint rules, generates 384-dimensional vector embeddings in Qdrant, and powers an AI reasoning assistant fortified against prompt injection.

```
Git Repository ──► Hardened Sandbox ──► Multi-Language AST ──► Property Knowledge Graph
                                    ──► OSV & Taint Scanner ──► Security Findings Matrix
                                    ──► Dense Embeddings   ──► Qdrant Vector Engine
                                                                       │
                                                                       ▼
                                                          GITTY-AI Unified Cockpit
```

---

## Cockpit Showcase

The GITTY-AI frontend is a high-density, real-time code intelligence workstation designed for security engineers and software architects.

### Unified Engineering Cockpit
The primary workstation combines the 2D Force-Directed Graph Canvas, Hierarchical Source Artifact Explorer, Depth-Filtered Telemetry Matrix, and AI Reasoning Core.

![GITTY-AI Cockpit Dashboard](docs/assets/readme/dashboard.png)
![GITTY-AI Call Paths](docs/assets/readme/call_paths.png)

---

### Cockpit Subsystems

| Subsystem | Screenshot | Description |
| :--- | :--- | :--- |
| **Interactive Graph Matrix** | ![Graph Matrix](docs/assets/readme/graph-matrix.png) | High-performance 2D canvas visualizing file and symbol topology. Features dynamic physics simulation, Level-of-Detail (LOD) node clustering, and progressive child expansion. |
| **Source Artifact Explorer** | ![Source Explorer](docs/assets/readme/source-explorer.png) | High-density hierarchical directory tree showing code artifacts, file-level node counts, active target repositories, and real-time HUD display filters. |
| **Security & Vulnerability HUD** | ![Security HUD](docs/assets/readme/security-hud.png) | Live vulnerability matrix displaying OSV CVE advisories, hazardous API calls (`eval`, `exec`, `shell=True`), hardcoded secret detections, and severity distribution. |
| **Reactor Core & AI Console** | ![Reactor Core](docs/assets/readme/gitty-core.png) | RAG-driven contextual code reasoning interface. Fenced with XML boundaries and enriched with direct AST symbol citations and similarity scores. |

---

## Key Capabilities

* **Secure Ingestion Engine**:
  * Shallow cloning (`--depth=1`) with configurable execution timeouts.
  * Strict loopback, RFC 1918, and AWS/GCP link-local metadata SSRF blocking.
  * Git command flag-injection defense (`--`) and symlink neutralization (`-c core.symlinks=false`).

* **Multi-Language AST Extraction**:
  * Native Python AST parser extracting functions, classes, decorators, docstrings, imports, and call sites.
  * Tree-sitter parsers supporting JavaScript, TypeScript, and Java syntax trees.
  * Automated dead-code detection (`DeadCodeDetectionService`) for uncalled functions and orphan classes.

* **Vulnerability & Secret Intelligence**:
  * Real-time querying against the **Google OSV (Open Source Vulnerabilities)** API for known package CVEs.
  * High-entropy regex pattern scanning for exposed API keys, private tokens, and credentials.
  * Hazardous API heuristic scanning (`eval`, `exec`, `shell=True`, `pickle`, `MD5`, `SHA1`, `DEBUG=True`).

* **Dual Property Graph Backends**:
  * **SQLite Engine**: Zero-dependency, lightweight, embedded graph backend with batched execution (`executemany`) and parameter limit safeguards.
  * **Neo4j Cluster**: Enterprise-grade Cypher property graph backend for large-scale graph traversals.

* **Hybrid Vector Search & RAG**:
  * 384-dimensional dense code embeddings indexed in **Qdrant**.
  * Cosine similarity scoring with SQLite embedding caching for deduplication.
  * XML boundary fencing (`<repository_untrusted_context>`) to neutralize prompt injection attacks.

* **Real-Time Reactive Streaming**:
  * Asynchronous task processing via **Celery** and **RabbitMQ**.
  * Real-time progress and terminal log broadcasting using **Redis Pub/Sub** and **Server-Sent Events (SSE)**.

---

## System Architecture

The following diagram illustrates the end-to-end dataflow across client layers, API gateways, worker tasks, databases, and external intelligence providers:

![GITTY-AI System Architecture](docs/assets/readme/architecture.png)

### High-Level Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT INTERFACE                              │
│              React 19 • TypeScript • Vite • Tailwind CSS                │
│    [ Interactive Graph ]   [ Source Explorer ]   [ Reactor Core RAG ]   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / SSE (Bearer JWT)
┌────────────────────────────────────▼────────────────────────────────────┐
│                          FASTAPI API GATEWAY                            │
│  - RFC 7519 JWT Authentication & PBKDF2 Password Hashing (600k rounds)  │
│  - IDOR-Protected Per-User Resource Authorization                       │
│  - REST Endpoints (/repositories, /graph, /chat, /search)               │
│  - Redis Pub/Sub Server-Sent Events (SSE) Multiplexer                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ AMQP Task Dispatch
┌────────────────────────────────────▼────────────────────────────────────┐
│                          CELERY WORKER FABRIC                           │
│  ┌─────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Hardened Ingestion      │  │ AST Symbol Extraction                │  │
│  │ (SSRF & Flag Guard)     │  │ (Python AST, JS/TS/Java Tree-sitter) │  │
│  └────────────┬────────────┘  └──────────────────┬───────────────────┘  │
│               │                                  │                      │
│  ┌────────────▼────────────┐  ┌──────────────────▼───────────────────┐  │
│  │ Vulnerability Engine    │  │ Semantic Embedding Pipeline          │  │
│  │ (Google OSV API & Taint)│  │ (384-d Chunker & SQLite Cache)       │  │
│  └─────────────────────────┘  └──────────────────────────────────────┘  │
└───────────────┬──────────────────────────┬───────────────────────┬──────┘
                │                          │                       │
┌───────────────▼───────────┐┌─────────────▼─────────┐┌───────────▼───────┐
│     GRAPH REPOSITORY      ││     VECTOR ENGINE     ││   MESSAGE FABRIC  │
│ SQLite Graph (Zero-Dep)   ││ Qdrant Vector Database││ RabbitMQ (Tasks)  │
│ or Neo4j (Cypher Engine)  ││ (384-d Cosine Metric) ││ Redis (SSE Stream)│
└───────────────────────────┘└───────────────────────┘└───────────────────┘
```

---

## How It Works

When an analysis job is initiated, GITTY-AI executes a 10-step asynchronous pipeline:

```
 [1. Ingest] ──► [2. Manifests] ──► [3. OSV Query] ──► [4. Security Scan] ──► [5. Dead Code]
      │
      ▼
 [6. AST Parse] ──► [7. Graph Commit] ──► [8. Chunk & Embed] ──► [9. Vector Upsert] ──► [10. SSE Complete]
```

1. **Repository Ingestion & Defense**: The URL is validated against SSRF blocklists (loopback, RFC 1918, cloud metadata) and command-injection patterns. Git performs a shallow clone (`--depth=1`) with symlinks disabled.
2. **Dependency Manifest Discovery**: Scans for ecosystem manifest files (`requirements.txt`, `Pipfile`, `pyproject.toml`, `package.json`, `pom.xml`).
3. **Google OSV Vulnerability Lookup**: Queries the live Google Open Source Vulnerabilities database for known CVEs and affected version ranges.
4. **Static Taint & Secret Analysis**: Scans source files with regex entropy heuristics for exposed credentials and detects unsafe primitives (`eval`, `exec`, `shell=True`, `pickle`).
5. **Dead Code Identification**: Analyzes intra-repository symbol references using `DeadCodeDetectionService` to highlight unused methods and unreachable classes.
6. **Deterministic AST Parsing**: Traverses syntax trees across Python, JavaScript, TypeScript, and Java to extract code entities, imports, inheritance, and call sites.
7. **Property Graph Construction**: Commits typed nodes (`Repository`, `File`, `Class`, `Function`, `Import`, `Call`) and edges (`CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `BELONGS_TO`) using batch transactions.
8. **Semantic Chunking & Embedding**: Chunks code into logical blocks and produces dense 384-dimensional vector embeddings, cached in SQLite to avoid recomputing duplicates.
9. **Qdrant Vector Indexing**: Upserts code embeddings and symbol metadata payloads into Qdrant collections.
10. **SSE Synchronization**: Streams real-time progress events over Redis Pub/Sub to the frontend dashboard, immediately rendering the newly mapped topology.

---

## Technology Stack

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **Frontend UI** | React 19, TypeScript, Vite, Tailwind CSS, Lucide React, Canvas API | High-performance interactive graph cockpit, live SSE event viewer, chat console |
| **API Gateway** | FastAPI, Starlette, Pydantic v2, Uvicorn, Python 3.11+ | Asynchronous REST gateway, JWT security, SSE stream endpoints |
| **Worker Fabric** | Celery, Kombu, RabbitMQ (AMQP) | Distributed task scheduling, background repository ingestion and parsing |
| **Graph Storage** | SQLite (default embedded), Neo4j 5+ (optional cluster) | Typed code property graph, relationship mapping, dependency hierarchy |
| **Vector Engine** | Qdrant, sentence-transformers (384-d dense vectors) | Semantic code search, RAG context retrieval, cosine similarity indexing |
| **Cache & Bus** | Redis 7+ | Real-time Pub/Sub log streaming, Celery task state cache |
| **Parsers** | Built-in Python `ast`, Tree-sitter (JS/TS/Java) | Deterministic symbol extraction, structural code intelligence |
| **Vulnerability** | Google OSV API, Static Regex Entropy Heuristics | Dependency CVE auditing, secrets scanning, hazardous API detection |

---

## Project Structure

```
GITTY-AI/
├── apps/
│   ├── api-gateway/         # FastAPI REST service & SSE streaming endpoints
│   │   ├── app/             # Application routers (auth, graph, chat, search, repos)
│   │   └── tests/           # Gateway unit and integration tests
│   ├── frontend/            # React 19 + TypeScript + Vite cockpit application
│   │   ├── src/             # Components (GraphCanvas, RepositorySidebar, TopNav, Chat)
│   │   └── public/          # Branding and static cockpit assets
│   └── worker/              # Celery background worker tasks and ingestion pipeline
│       └── tasks/           # Ingestion, AST parsing, OSV querying, vectorization
├── libs/
│   ├── ai/                  # RAG prompt builder, XML fencing, embedding generation
│   ├── auth/                # PBKDF2 password hashing, JWT RFC 7519 tokens, user models
│   ├── config/              # Centralized Pydantic application settings
│   ├── events/              # Redis Pub/Sub event broadcasting and SSE abstractions
│   ├── exceptions/          # Standardized domain exception hierarchy
│   ├── graph/               # Graph database clients (SQLite batch client and Neo4j driver)
│   ├── logging/             # Structured JSON logging configurations
│   ├── models/              # Pydantic schemas (Graph, Security, Repository, User)
│   └── scanner/             # AST parsers, OSV vulnerability client, dead code analyzer
├── infrastructure/
│   ├── compose/             # Docker Compose configurations (dev, staging, services)
│   └── docker/              # Dockerfiles for gateway, worker, and frontend
├── docs/
│   └── assets/readme/       # Verified cockpit screenshots and architecture diagrams
└── tests/                   # End-to-end and integration test suite (149 tests)
```

---

## Getting Started

### Prerequisites

* **Python 3.11+** (or Python 3.12 / 3.13)
* **Node.js 18+** and **npm**
* **Git** installed on your system path
* **Docker & Docker Compose** (for Redis, RabbitMQ, and Qdrant)

---

### Step 1: Start Infrastructure Services

Launch Redis, RabbitMQ, and Qdrant via Docker Compose:

```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d redis rabbitmq qdrant
```

Verify that all three services are healthy:
* **Redis**: `localhost:6379`
* **RabbitMQ**: `localhost:5672` (Management UI: `http://localhost:15672` default `guest/guest`)
* **Qdrant**: `localhost:6333` (Web Dashboard: `http://localhost:6333/dashboard`)

---

### Step 2: Set Up Backend Virtual Environment

```bash
# Create and activate virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate

# Install application dependencies and local libraries
pip install -r apps/api-gateway/requirements.txt
pip install -r apps/worker/requirements.txt
pip install -e ./libs/config -e ./libs/logging -e ./libs/exceptions -e ./libs/models -e ./libs/graph -e ./libs/ai -e ./libs/events -e ./libs/auth -e ./libs/scanner
```

---

### Step 3: Run the API Gateway

```bash
# Windows PowerShell:
$env:PYTHONPATH="."
python -m uvicorn app.main:app --app-dir apps/api-gateway --host 0.0.0.0 --port 8000 --reload

# Linux / macOS:
PYTHONPATH=. python -m uvicorn app.main:app --app-dir apps/api-gateway --host 0.0.0.0 --port 8000 --reload
```

* API Gateway: `http://localhost:8000`
* Interactive OpenAPI Documentation: `http://localhost:8000/docs`

---

### Step 4: Run the Celery Worker

In a separate terminal (with the virtual environment activated):

```bash
# Windows PowerShell:
$env:PYTHONPATH="."
celery -A apps.worker.worker_app worker --loglevel=info -P threads

# Linux / macOS:
PYTHONPATH=. celery -A apps.worker.worker_app worker --loglevel=info
```

---

### Step 5: Start the Frontend Cockpit

In a third terminal:

```bash
cd apps/frontend
npm install
npm run dev
```

Open your browser and navigate to **`http://localhost:5173`**.

> [!TIP]
> **Zero-Friction Local Development**: By default, local development is configured with `DEV_AUTH_BYPASS=true`, allowing developers to directly inspect graphs, trigger repository ingestion, and query the AI console without login gates. Production instances enforce strict RFC 7519 JWT verification.

---

### Full Containerized Deployment

To launch the complete GITTY-AI stack (Gateway, Worker, Frontend, Redis, RabbitMQ, Qdrant) inside Docker containers:

```bash
docker compose -f infrastructure/compose/docker-compose.dev.yml up --build
```

---

## Configuration

Environment variables can be configured in a root `.env` file:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `staging`, `production`) |
| `DEV_AUTH_BYPASS` | `true` (dev) / `false` (prod) | Allows bypassing frontend auth modals during local UI development |
| `JWT_SECRET_KEY` | `*secure-random-key*` | HMAC-SHA256 secret key for signing authentication tokens |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | Validity period of issued JWT bearer tokens |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672//` | AMQP broker connection string for Celery tasks |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis instance for real-time SSE pub/sub log streaming |
| `GRAPH_STORAGE_TYPE` | `sqlite` | Graph storage backend: `sqlite` (zero-dep) or `neo4j` |
| `SQLITE_DB_PATH` | `data/gitty_graph.db` | File path for the embedded SQLite graph database |
| `NEO4J_URI` | `bolt://localhost:7687` | Connection URI when using Neo4j graph cluster |
| `QDRANT_HOST` | `localhost` | Hostname of the Qdrant vector database |
| `QDRANT_PORT` | `6333` | REST port of the Qdrant vector database |
| `OPENAI_API_KEY` | *(Optional)* | API key for external LLM reasoning in the Reactor Core |

---

## Security Architecture

GITTY-AI applies defense-in-depth principles across every phase of code ingestion, storage, and AI reasoning:

```
Untrusted Input ──► [ SSRF Validator ] ──► [ Flag Neutralizer ] ──► [ Isolated Subprocess ]
                                                                             │
LLM Context     ◄── [ XML Isolation ]  ◄── [ IDOR Ownership ]  ◄── [ Secure Storage ]
```

1. **SSRF & Network Defense**:
   * Repository URLs are resolved and audited against reserved network blocks before any outbound network call.
   * Blocks RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.1`, `localhost`), and cloud metadata APIs (`169.254.169.254`).
2. **Git Argument Injection Neutralization**:
   * Ingestion parameters starting with `-` or `--` are immediately rejected.
   * Git clones execute with explicit `--` delimiters and `-c core.symlinks=false` to prevent symlink traversal and arbitrary command execution.
3. **Prompt Injection Boundary Fencing**:
   * Untrusted source code passed to the LLM context is strictly encapsulated within `<repository_untrusted_context>` XML delimiter tags.
   * Hardened system prompts instruct the LLM to treat untrusted context purely as inert data to prevent prompt takeover via malicious repository comments or README files.
4. **Authentication & IDOR Data Isolation**:
   * Cryptographic password storage using `hashlib.pbkdf2_hmac` with **600,000 rounds** of SHA-256 and unique 16-byte random salts.
   * Fast-path owner validation dependencies (`require_repository_owner`, `require_session_owner`) prevent Insecure Direct Object References (IDOR).

---

## Verification & Testing

The repository maintains an automated test suite verifying security controls, ingestion pipelines, database batching, and vector search:

```bash
# Run the complete test suite
pytest -v tests/
```

### Verified Test Coverage

* **Security & Ingestion Safeguards** (`tests/test_scanner_security.py`):
  * URL format verification, SSRF IP-range blocking, Git command-line injection defense, and symlink flags.
* **Authentication & Authorization** (`tests/test_auth_api.py`):
  * PBKDF2 key derivation, JWT RFC 7519 encoding/expiration, duplicate user rejection, and per-user IDOR enforcement.
* **Graph Batching & Integrity** (`tests/test_sqlite_batching.py`):
  * Large-scale batch inserts (`executemany`) and chunked deletions avoiding SQLite parameter limit errors.
* **Worker & Pipeline Tasks** (`tests/test_ingestion_worker.py`, `tests/test_vector_worker.py`):
  * End-to-end repository ingestion, idempotent re-indexing, and SSE progress pub/sub verification.
* **RAG & Search Quality** (`tests/test_prompt_builder.py`, `tests/test_search_endpoints.py`, `tests/test_chat_endpoints.py`):
  * XML boundary sanitization, token budget management, and Qdrant semantic search retrieval.

---

## Contributors

* **Nikhil Singh** ([@s-nikhil2005](https://github.com/s-nikhil2005))
* **tigpy** ([@tigpy](https://github.com/tigpy))

---

## License

This project is licensed under the MIT License.
