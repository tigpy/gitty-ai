FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first to cache them
COPY apps/api-gateway/requirements.txt ./apps/api-gateway/requirements.txt
RUN pip install --no-cache-dir -r apps/api-gateway/requirements.txt

# Copy source code and libraries
COPY libs/ ./libs/
COPY services/ ./services/
COPY apps/api-gateway/ ./apps/api-gateway/

# Install local libs
RUN pip install -e ./libs/config -e ./libs/logging -e ./libs/exceptions -e ./libs/models -e ./libs/graph -e ./libs/ai -e ./libs/events || true

EXPOSE 8000

ENV PYTHONPATH=/app

CMD ["python", "apps/api-gateway/app/main.py"]
