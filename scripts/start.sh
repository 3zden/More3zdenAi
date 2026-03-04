#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# More3zdenAI – Quick Start Script
# Run this once to get the full stack running locally.
# ─────────────────────────────────────────────────────────────────────────────
set -e

OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2}

echo "🚀 Starting More3zdenAI..."

# 1. Copy .env if not present
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ Created .env from .env.example — edit it before going to production!"
fi

# 2. Build & start services
echo "🐳 Building and starting Docker services..."
docker compose up -d --build db redis ollama

# 3. Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
until docker compose exec ollama curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 3
  echo "  still waiting..."
done
echo "✅ Ollama is ready"

# 4. Pull the LLM model
echo "📥 Pulling Ollama model: $OLLAMA_MODEL (this may take a few minutes)..."
docker compose exec ollama ollama pull $OLLAMA_MODEL
echo "✅ Model $OLLAMA_MODEL downloaded"

# 5. Start backend (builds FAISS index on first run)
echo "🔧 Starting Django backend..."
docker compose up -d --build backend

echo "⏳ Waiting for backend to be healthy..."
until docker compose exec backend curl -sf http://localhost:8000/api/health/ > /dev/null 2>&1; do
  sleep 5
  echo "  still starting (building FAISS index)..."
done
echo "✅ Backend is healthy"

# 6. Start frontend
echo "🎨 Starting Next.js frontend..."
docker compose up -d --build frontend nginx

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ More3zdenAI is running!"
echo ""
echo "  🌐 Frontend:  http://localhost"
echo "  🔌 API:       http://localhost/api/"
echo "  🏥 Health:    http://localhost/api/health/"
echo "  🛠  Admin:     http://localhost/admin/"
echo "═══════════════════════════════════════════════════"
