# GITTY-AI Roadmap & Engineering Status

This document records the verified status of features in GITTY-AI, clearly distinguishing completed and implemented capabilities from planned future extensions.

---

## 1. Current Verified Implementation (Completed)

### Security & Ingestion Hardening
- [x] **SSRF & Command Flag Defense**: Comprehensive URL validation preventing command line injection (`--upload-pack`, `-u`) and blocking SSRF targets (loopback, private RFC 1918 subnets, cloud metadata 169.254.169.254).
- [x] **Git Isolation**: Ingestion invokes shallow clones (`--depth=1`) with `-c core.symlinks=false`, explicit `--` end-of-options delimiters, and execution timeouts.
- [x] **Native Authentication**: Zero-dependency RFC 7519 HMAC-SHA256 JWT tokens and PBKDF2-HMAC-SHA256 (600,000 iterations) password hashing with cryptographic salts.
- [x] **IDOR Protection**: Strict per-user ownership verification across all repository actions, graph expansions, chat sessions, and SSE progress channels.
- [x] **Prompt Injection Defense**: Dual-layer mitigation utilizing system prompt security policies and XML boundary fencing (`<repository_untrusted_context>`) to prevent code comments from hijacking LLM reasoning.

### Performance & Scalability
- [x] **Batch Database Operations**: Added `add_nodes_batch` and `add_edges_batch` with single-transaction commits in `SQLiteGraphRepository`.
- [x] **Chunked SQL Cleanup**: Chunked deletions in batches of 400 parameters to prevent SQLite variable limit exhaustion on large codebases.
- [x] **Native Cypher Graph Traversal**: Replaced slow N+1 Python loops in Neo4j with native Cypher traversals (`shortestPath`, variable-length relationships).
- [x] **Async Redis SSE**: Migrated Server-Sent Events from synchronous blocking Redis to `redis.asyncio` to prevent FastAPI thread pool exhaustion.
- [x] **Celery Resiliency**: Configured task timeouts (`time_limit=600`), retry bounds (`max_retries=2`), and idempotent pre-indexing cleanup.

### Intelligence & Security Analysis
- [x] **Google OSV Integration**: Real-time dependency vulnerability lookup against Google OSV API with 2-second timeout, in-memory caching, and local fallback database.
- [x] **Dangerous API & Secret Detection**: Static detection for hardcoded secrets (API keys, AWS credentials) and hazardous operations (`eval`, `exec`, `subprocess(shell=True)`).
- [x] **Dead Code Analysis**: Detection of functions and symbols with zero inbound references.
- [x] **Semantic Vector Search**: SentenceTransformer embeddings cached in SQLite and indexed in Qdrant with real cosine similarity score propagation.
- [x] **Multi-Language Graceful Degradation**: Safely indexes Java, JavaScript, and TypeScript repositories without crashing the worker pipeline when Tree-sitter is uninstalled.

### Frontend Client
- [x] **React 19 + Vite Dark Mode UI**: Interactive graph explorer with Lucide icons.
- [x] **Client Auth Integration**: Integrated Sign In and Registration modals with JWT local storage and authenticated fetch headers.
- [x] **Live Terminal Streaming**: Real-time progress monitoring via Server-Sent Events.

---

## 2. Planned Future Enhancements (Roadmap)

### Phase 1: Deep Polyglot Parsing (Q3 2026)
- [ ] Install Tree-sitter binaries for full AST generation across JavaScript, TypeScript, Go, and Java.
- [ ] Add cross-language import resolution (e.g. Python microservice calling Go gRPC endpoint).

### Phase 2: Enterprise Identity & Governance (Q4 2026)
- [ ] OAuth2 / GitHub SSO integration alongside native username/password auth.
- [ ] Organization-level multi-tenancy and team RBAC (Admin, Security Lead, Developer).
- [ ] Audit trail logging for all repository scans and compliance reports (SOC 2, ISO 27001).

### Phase 3: Automated Remediation Agents (Q1 2027)
- [ ] Multi-file automated pull request generation for CVE remediations.
- [ ] Interactive refactoring sandbox for dead-code pruning.
- [ ] Integration with GitHub Actions and GitLab CI for automatic PR security scanning.
