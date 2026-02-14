FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    tesseract-ocr \
    tesseract-ocr-fas \
    tesseract-ocr-eng \
    ffmpeg

# Set work directory
WORKDIR /app

# Copy requirements from deployment folder
COPY deployment/requirements.txt .

# Install Python dependencies in stages to avoid resolution-too-deep
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Stage 1: Core dependencies (numpy first to avoid conflicts)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "numpy>=1.24.3,<2.0.0"

# Stage 2: Install from requirements with increased timeout and retries
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout 300 \
    --retries 5 \
    -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 7001

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7001"]
