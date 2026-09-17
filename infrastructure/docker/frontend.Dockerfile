# Multi-stage Dockerfile for GITTY-AI React/Vite Frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY apps/frontend/package*.json ./apps/frontend/
RUN cd apps/frontend && npm install

# Copy source and build
COPY apps/frontend/ ./apps/frontend/
RUN cd apps/frontend && npm run build

# Production stage using Nginx
FROM nginx:alpine

COPY --from=builder /app/apps/frontend/dist /usr/share/nginx/html
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
