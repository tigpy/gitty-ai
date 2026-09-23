# Deployment

Compose files:

- Local infrastructure only: `docker compose -f infrastructure/compose/docker-compose.yml up -d redis rabbitmq qdrant`
- Dev application stack: `docker compose -f infrastructure/compose/docker-compose.yml -f infrastructure/compose/docker-compose.dev.yml up --build`
- Production file: `docker compose -f infrastructure/compose/docker-compose.yml -f infrastructure/compose/docker-compose.prod.yml up -d`

The production file sets `ENV=production` and `DEV_AUTH_BYPASS=false`. It requires `JWT_SECRET_KEY` and `NEO4J_PASSWORD` to be present in the environment and does not accept the placeholders listed in `libs/config/config_loader.py`. `EMBEDDING_PROVIDER` is `sentence-transformers`. `GRAPH_MODE` defaults to `sqlite` unless you set `neo4j`.

These commands were not executed as a release verification. A successful `docker compose up` is not claimed.
