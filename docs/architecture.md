# GITTY-AI System Architecture

This document provides a detailed technical description of the architecture, data structures, and runtime workflows implemented in **GITTY-AI**.

---

## 1. High-Level Architecture Overview

GITTY-AI is built around a decoupled service-oriented architecture designed for deterministic code analysis, semantic search, graph relationship intelligence, and cybersecurity vulnerability detection.

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

---

## 2. Core Subsystems

### 2.1 API Gateway (`apps/api-gateway`)
- **Framework**: FastAPI (Python 3.11 / 3.13 compatible).
- **Authentication**: Native PBKDF2-HMAC-SHA256 (600,000 iterations) password hashing + RFC 7519 HMAC-SHA256 signed JWT tokens.
- **Authorization**: Granular per-user data isolation eliminating Insecure Direct Object References (IDOR). All repository graphs, analysis jobs, and chat sessions require verified ownership.
- **Real-Time Progress**: Server-Sent Events (`/api/v1/repositories/{id}/progress`) powered by `redis.asyncio` to prevent event-loop thread blocking.

### 2.2 Worker Pipeline (`apps/worker/worker_app.py`)
- **Task Runner**: Celery backed by RabbitMQ broker and Redis result backend.
- **Ingestion Steps**:
  1. **Validation**: Remote URL validated against SSRF targets, private RFC 1918 IPs, loopbacks, and flag injection (`--upload-pack`, `-u`).
  2. **Shallow Clone**: `git clone --depth=1 -c core.symlinks=false -- <url> <dest>` executed with execution timeouts.
  3. **File Discovery**: `FileDiscoveryService` categorizes source code, documentation, and config files while filtering `.git`, `node_modules`, `venv`, and binary artifacts.
  4. **AST Parsing**: Python uses the built-in `ast` module. JavaScript, TypeScript, and Java use the Tree-sitter parsers in `services/parser_service` when those grammars import. A missing grammar does not by itself invent nodes.
  5. **Security Scanning**:
     - **Dependency scanner**: Static parse of the manifests listed in the README. Exact versions are sent to the OSV API with ecosystem `PyPI`, `npm`, or `Maven`. Lookup failure is `unavailable` or `partial`, not an empty clean report. A three-package local seed still flags old `requests`, `pyyaml`, and `urllib3`.
     - **Secret Detector**: Regex and entropy detection of AWS tokens, GitHub tokens, JWTs, and private keys.
     - **Dangerous API Detector**: Identifies `eval`, `exec`, `os.system`, `subprocess(shell=True)`, insecure deserialization (`pickle`), and weak cryptographic hashing (`md5`, `sha1`).
  6. **Graph Construction**: Batch-accumulates graph nodes and edges and commits them via bulk SQL transactions.
  7. **Vector Indexing**: Semantically chunks functions, classes, files, documentation, and security findings. Generates 384-dimensional embeddings stored in Qdrant with SQLite caching.

### 2.3 Graph Engine (`services/graph_service`)
- **Dual-Backend Support**:
  - **SQLite**: Zero-dependency local graph engine using batched `executemany` statements and 400-variable chunked deletions to avoid SQLite parameter limits.
  - **Neo4j**: Enterprise graph database using native Cypher traversals (`shortestPath`, `MATCH path = (start)-[*]->(target)`) avoiding N+1 Python iteration overhead.

### 2.4 Vector Search & RAG (`services/vector_service`, `services/rag_service`)
- **Embeddings**: `SentenceTransformerProvider` loads `all-MiniLM-L6-v2` (384 dimensions) when that provider is selected. It does not fall back to hash vectors. `MockEmbeddingProvider` runs only when `EMBEDDING_PROVIDER=mock` and is rejected in production. The model was not loaded in the workspace that produced the M7 checkpoint.
- **Vector Store**: Qdrant. Upsert and search check the configured dimension. Collection setup does not fail the process solely because Qdrant is down; a later read or write does.
- **Hybrid context**: Vector hits are seeds. `GraphContextExpander` adds a bounded set of existing graph relationships. Limits are `RAG_MAX_GRAPH_SEEDS`, `RAG_MAX_GRAPH_DEPTH`, `RAG_MAX_GRAPH_NODES`, and `RAG_MAX_GRAPH_RELATIONSHIPS`.
- **Prompt construction**: `PromptBuilder` assigns a random boundary id and places repository and graph text in an untrusted region. The system prompt does not contain that text. This was tested structurally. It was not tested by asking a live model to ignore the boundary.

### 2.5 Frontend Client (`apps/frontend`)
- **Stack**: React 19 + TypeScript + Vite.
- **Visuals**: Lucide icons, custom glassmorphism dark mode UI.
- **Capabilities**:
  - Full user authentication flow (Registration, Sign In, JWT persistence).
  - Force-directed interactive graph visualization.
  - Live streaming log terminal (Server-Sent Events).
  - Code intelligence AI chat panel with clickable file and symbol citations.

---

## 3. Data Flow

### Ingestion Flow
```
User (UI) 
  --> POST /api/v1/repositories/analyze {url}
  --> Gateway validates URL & registers repo ownership
  --> Celery task 'gitty.tasks.index_repository' dispatched
  --> Worker clones shallow repo
  --> Scanner -> AST Parser -> Security Analyzer -> Graph Builder -> Vector Indexer
  --> Worker publishes live status via Redis pub/sub
  --> UI consumes progress via SSE stream
```

### Retrieval-Augmented Generation (RAG) Flow
```
User asks question in ChatPanel
  --> POST /api/v1/chat/sessions/{id}/messages
  --> Gateway verifies session ownership
  --> Semantic search in Qdrant retrieves code and document chunks
  --> GraphContextExpander adds a bounded set of graph relationships, or keeps the vector chunks if the graph lookup fails
  --> PromptBuilder places both in a randomly delimited untrusted region
  --> LLM provider generates an answer
  --> Response persisted to the session and returned to the UI
```
