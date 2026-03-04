FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Data directory for FAISS index
RUN mkdir -p /app/data

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Startup: migrate → build index → serve
CMD ["sh", "-c", "\
    python manage.py migrate --noinput && \
    python -c \"from rag.vector_store import FAISSVectorStore; s=FAISSVectorStore(); s.load_or_build()\" && \
    gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 --log-level info \
"]
