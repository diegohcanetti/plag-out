# ==========================================
# Phase 1: Build & Python Dependency caching
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies to a local target folder to enable clean caching
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# Phase 2: Production Execution Environment
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install system runtime libraries (PostGIS / Geospatial bindings)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgeos-c1v5 \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . .

# Set path variable to load pip packages correctly
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Default environment variables
ENV PORT=8000
ENV HOST=0.0.0.0
ENV WORKERS_COUNT=4

EXPOSE 8000

# Start server using high-performance Gunicorn with Uvicorn worker threads
CMD gunicorn api.main:app \
    --bind ${HOST}:${PORT} \
    --workers ${WORKERS_COUNT} \
    --worker-class uvicorn.workers.UvicornWorker \
    --threads 2 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
