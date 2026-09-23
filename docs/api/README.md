# API

The only HTTP API in this repository is the FastAPI gateway.

- Base URL in local development: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `GET /api/v1/health`
- Auth: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- Repository, graph, search, RAG, and chat routes are under `/api/v1` and require a bearer token unless `DEV_AUTH_BYPASS=true` in development.

There is no Express auth service. Authentication is implemented in `libs/auth` and `apps/api-gateway/app/api/v1/auth.py`.
