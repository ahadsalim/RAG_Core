FROM 10.10.10.111:5001/library/python:3.11-slim

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
    pip install --upgrade pip setuptools wheel \
    --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
    --trusted-host 10.10.10.111

# Stage 1: Download sentence-transformers offline packages from nginx
RUN apt-get update && apt-get install -y wget && \
    mkdir -p /tmp/pypi-offline && \
    wget -q -r -np -nH --cut-dirs=1 -R "index.html*" \
    http://10.10.10.111/pypi-offline/ -P /tmp/ && \
    apt-get remove -y wget && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Stage 2: Core dependencies (numpy first to avoid conflicts)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "numpy>=1.24.3,<2.0.0" \
    --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
    --trusted-host 10.10.10.111

# Stage 3: Install sentence-transformers from offline packages
RUN pip install --no-cache-dir \
    --no-index \
    --find-links /tmp/pypi-offline/ \
    sentence-transformers==5.2.3

# Stage 4: Install remaining requirements from devpi
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout 300 \
    --retries 5 \
    --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
    --trusted-host 10.10.10.111 \
    -r requirements.txt

# Clean up offline packages
RUN rm -rf /tmp/pypi-offline

# Copy application code
COPY . .

# Copy and set entrypoint script
COPY deployment/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 7001

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7001"]
