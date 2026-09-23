# GITTY-AI

Code intelligence service for a repository: local developer analysis tool, property graph, vector search, and a RAG chat path. This document describes the implementation in this repository. It is not a production-verification report.

## Overview

The application operates as a local developer analysis tool. A developer opens the web interface, inputs a repository URL, and begins analysis immediately without requiring user accounts, authentication tokens, or login screens.

The API gateway is FastAPI. Background ingestion is a Celery worker. A repository clone is parsed into a property graph (SQLite by default, Neo4j when `GRAPH_MODE=neo4j`). Source chunks are embedded and stored in Qdrant. Chat and RAG retrieve those chunks, then add a bounded set of graph relationships, then build a prompt. The LLM is a separate provider (`ollama`, `openai`, `gemini`, `claude`, or `mock`).

```
Client (React @ localhost:5173)
    |  HTTP (no auth / no Bearer token)
API gateway (FastAPI @ localhost:8000)
    |-- repositories, graph, search, RAG, chat
    |
Celery worker
    |-- clone, parse, graph commit, embed, security scan
    |
SQLite or Neo4j          Qdrant                 Redis / RabbitMQ
```

## Major capabilities

- Local developer analysis: immediate repository ingestion and exploration without registration or JWTs.
- Clone URLs are checked for SSRF, including DNS resolution and an HTTP redirect probe, before git runs.
- Python AST plus Tree-sitter parsers for JavaScript, TypeScript, and Java. The graph stores `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, and `BELONGS_TO` edges that those parsers emit.
- Vector search over code and documentation chunks.
- Hybrid RAG: vector hits are seeds; a bounded graph walk adds structural context.
- Static dependency manifest parsing and OSV lookups for exact versions.
- Static rules for a small set of dangerous Python calls and high-entropy secret patterns.

The React UI in `apps/frontend` talks directly to the gateway without Authorization headers. Screenshots under `docs/assets/readme/` are interface illustrations, not evidence that a control works.

## Security model

These controls reduce specific classes of bugs. They do not make the system fully secure, and they have not been proven against every model or every deployment.

### Local Tool Deployment

GITTY AI is designed as a local developer analysis tool bound to localhost (`127.0.0.1`). There are no user accounts, passwords, JWT tokens, or authentication screens. Unrelated security controls remain strictly enforced. Production startup rejects placeholder Neo4j passwords and `EMBEDDING_PROVIDER=mock`.

### Repository isolation

Repository boundary isolation is strictly preserved: a node traversal is allowed only when the node belongs to the requested repository (`_require_node_in_repository`). Graph expansion during RAG uses the repository id of the request and does not follow a node whose `CONTAINS` chain belongs to another repository.

### SSRF and git clone

`prepare_repository_clone_url` rejects non-http(s) schemes, credentials in the URL, loopback, private, link-local, multicast, and reserved addresses, and obfuscated IP forms. The host is resolved with `getaddrinfo` and every answer is checked. Redirects on the git discovery URL are probed and must stay on public addresses. The clone runs with `core.symlinks=false`, `credential.helper` empty, `http.followRedirects=false`, and `--`. This is not a full sandbox. A production deployment was not executed in this workspace.

### Embeddings

`EMBEDDING_PROVIDER` defaults to `sentence-transformers` with model `all-MiniLM-L6-v2` and `EMBEDDING_DIMENSIONS=384`. The worker calls `ensure_ready()` before indexing. If the real provider cannot load, indexing fails. It does not substitute hash vectors.

`EMBEDDING_PROVIDER=mock` is used only when set explicitly. It returns deterministic non-semantic vectors and is rejected when `ENV=production`. Qdrant writes and searches reject vectors whose length does not match the configured dimension. Live MiniLM inference was not run in this workspace because `sentence-transformers` was not installed. The optional test that would load it is skipped.

### Prompt injection

`PromptBuilder` puts repository text, graph text, and chat history in regions with a new random boundary id per builder instance. Metadata is escaped. System instructions are a separate channel and do not contain retrieved source. The same builder is used for RAG and chat.

This is a structural control. Tests check escaping, boundary breakout, and that repository text is absent from the system prompt. No live LLM call was used to show that a model will obey the separation. A model can still follow instructions that appear inside the data region.

### Hybrid RAG

Vector retrieval selects the relevant chunks. `GraphContextExpander` then walks existing graph edges from those chunks:

- relationships used: `CONTAINS`, `IMPORTS`, `CALLS`, `BELONGS_TO`, `INHERITS`
- defaults: 5 seeds, depth 2, 24 related nodes, 32 relationships
- results are deduplicated and capped again by the prompt character budget
- graph text is marked `origin="graph"` and stays in the untrusted region
- if the graph is missing, a seed cannot be resolved, or a lookup throws, the vector chunks are kept and no relationship is invented

There is no second semantic re-ranker. Depth 2 is enough to move from a function to a call node to a callee. It is not a whole-repository walk.

### Dependency security

Manifests are parsed as text. Package managers are not installed or executed. See the support matrix below. OSV is queried at `https://api.osv.dev/v1/query` only when an exact version is known. A timeout or HTTP failure sets the scan to `unavailable` or `partial` and adds an explicit finding. That state is not reported as "0 vulnerabilities".

A local seed still flags older `requests`, `pyyaml`, and `urllib3` releases. That seed is not a vulnerability database.

One live OSV query was executed from this workspace: npm `lodash` `4.17.20` returned advisories, including `GHSA-29mw-wpgm-hmr9`. PyPI and Maven were not live-queried. Qdrant, Neo4j, and a production compose stack were not live-verified here.

## Dependency coverage

Supported, and only when the parser recognizes the file:

| Ecosystem | Manifests |
|---|---|
| PyPI | `requirements.txt`, `requirements/*.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`, `uv.lock` |
| npm | `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml` |
| Maven coordinates | `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradle.lockfile` |

Recognized but not parsed: `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`, `packages.config`, `Podfile`.

Limitations:

- Nested `-r` requirement includes are ignored.
- Version ranges are stored and are not sent to OSV as if they were versions.
- Yarn and pnpm locks are read with line patterns, not a full lockfile model.
- Gradle version catalogs and Maven BOMs are not resolved. `dependencyManagement` entries are skipped.
- Transitive packages are reported only when a parsed lockfile lists them and they are not also declared as direct.
- `node_modules` is not walked. Symlinked manifests are not read.

## Configuration

Settings live in `libs/config/config_loader.py` and are read from the environment or a root `.env`. Copy `.env.example`. Names below are the names the code reads.

| Variable | Default | Notes |
|---|---|---|
| `ENV` | `development` | `production` runs `validate_production_security()` |
| `DEV_AUTH_BYPASS` | `false` | Development identity only. Rejected in production |
| `JWT_SECRET_KEY` | insecure local default | Production requires a unique secret of at least 32 characters |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | 7 days |
| `JWT_ALGORITHM` | `HS256` | |
| `GRAPH_MODE` | `sqlite` | `neo4j` selects the Neo4j repository |
| `SQLITE_DB_PATH` | `gitty_graph.db` | |
| `NEO4J_URI` | `bolt://localhost:7687` | |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD` | `gitty_password` | Rejected in production. Also rejected: `neo4j`, `password`, and the `.env.example` placeholder |
| `QDRANT_HOST` | `localhost` | |
| `QDRANT_PORT` | `6333` | |
| `EMBEDDING_PROVIDER` | `sentence-transformers` | `mock` is explicit and rejected in production |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | |
| `EMBEDDING_DIMENSIONS` | `384` | Must match the model and the Qdrant collections |
| `RAG_MAX_GRAPH_SEEDS` | `5` | |
| `RAG_MAX_GRAPH_DEPTH` | `2` | |
| `RAG_MAX_GRAPH_NODES` | `24` | |
| `RAG_MAX_GRAPH_RELATIONSHIPS` | `32` | |
| `LLM_PROVIDER` | `ollama` | `openai`, `gemini`, `claude`, or `mock` |
| `LLM_MODEL` | `llama3` | |
| `OLLAMA_URI` | `http://localhost:11434` | |
| `CHAT_HISTORY_LIMIT` | `10` | |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | There is no `REDIS_URL` setting |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` | `localhost` / `5672` | There is no `RABBITMQ_URL` setting |
| `CORS_ORIGINS` | local Vite and port 3000 origins | Comma-separated |

`docker-compose.dev.yml` sets `ENV=development` and the dev Neo4j password. `docker-compose.prod.yml` sets `ENV=production`, `DEV_AUTH_BYPASS=false`, and requires `JWT_SECRET_KEY` and `NEO4J_PASSWORD` from the environment. Neither file was started in this workspace.

## Local development

Prerequisites: Python 3.10 or newer, Node.js 18 or newer for the UI, Git, and Docker if you want Redis, RabbitMQ, and Qdrant. The automated suite in this workspace ran on Python 3.10.

```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d redis rabbitmq qdrant
python -m venv venv
source venv/bin/activate
pip install -r apps/api-gateway/requirements.txt
pip install -r apps/worker/requirements.txt
cp .env.example .env
PYTHONPATH=. python -m uvicorn app.main:app --app-dir apps/api-gateway --host 0.0.0.0 --port 8000 --reload
PYTHONPATH=. celery -A apps.worker.worker_app worker --loglevel=info
```

Frontend:

```bash
cd apps/frontend
npm install
npm run dev
```

The UI listens on `http://localhost:5173`. The API is `http://localhost:8000`. OpenAPI is `/docs`.

Login is required unless you set `DEV_AUTH_BYPASS=true` while `ENV=development`.

`sentence-transformers` is not pinned in the API requirements. Install it before indexing if you use the default embedding provider. Without it, indexing fails instead of writing fake vectors.

## Testing

From the repository root:

```bash
pytest
```

`pytest.ini` puts the application packages on `pythonpath`.

Focused groups:

```bash
pytest tests/test_auth_security.py tests/test_auth_api.py
pytest tests/test_ssrf_validation.py tests/test_scanner_security.py
pytest tests/test_embedding_provider.py
pytest tests/test_prompt_injection.py tests/test_prompt_builder.py
pytest tests/test_hybrid_rag.py tests/test_rag_service.py tests/test_chat_service.py
pytest tests/test_graph_endpoints.py tests/test_graph_service.py
pytest tests/test_dependency_scanner.py tests/test_security_analysis_service.py
```

Known results at this release checkpoint, on Python 3.10 without `sentence-transformers`, Qdrant, Neo4j, or a live LLM:

- `test_optional_live_minilm_inference` is skipped.
- `test_local_file_walker_basic` fails. The walker still returns `ignored_dir/secret.txt`.
- `test_get_repository_graph_initial` fails. The graph response includes 4 nodes where the test expects 3.

Those two failures were already present before this documentation pass. They were not changed here.

Qdrant client construction in some tests warns that it cannot read a server version. That is an environment warning, not a passing live Qdrant check.

## Known limitations

- Prompt boundaries are not a guarantee that a model will ignore repository text.
- Dependency coverage is the matrix above, not every ecosystem and not every transitive package.
- Graph expansion only sees edges the parser stored.
- Embeddings are real only when the sentence-transformers provider loads. That load was not executed here.
- OSV was live-checked for one npm package only.
- Neo4j, Qdrant, Redis, RabbitMQ, and the production compose file were not started here.
- `libs/ai/rag.HybridRetriever` is not the RAG implementation. Calling it raises. Chat and RAG go through `RAGService` and `ChatService`.

## Project layout

```
apps/api-gateway/     FastAPI routes
apps/worker/          Celery tasks
apps/frontend/        React UI
libs/auth/            Passwords, JWT, ownership dependencies
libs/config/          Settings and production checks
libs/shared_kernel/   Repository URL validation
services/graph_service/
services/vector_service/
services/rag_service/ RAG, chat, prompt builder, graph expansion
services/security_service/  Rules and dependency scanner
services/scanner_service/   Clone and file walk
infrastructure/compose/     Docker Compose files
tests/
```

## Contributors

- Nikhil Singh ([@s-nikhil2005](https://github.com/s-nikhil2005))
- tigpy ([@tigpy](https://github.com/tigpy))

## License

MIT. See the repository license file if one is present. The absence of a `LICENSE` file in the tree means the MIT claim above is the historical project statement, not a file this checkpoint added.
