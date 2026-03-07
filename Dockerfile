FROM python:3.13-slim AS base

WORKDIR /app

# System dependencies for cryptography, paramiko, psutil
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create required directories
RUN python3 -c "from config import cfg; cfg.ensure_dirs()"

ENV ALII_WORKDIR=/app

# Alfred orchestrator port
EXPOSE 7000

# Health check via Alfred status endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:7000/status')" || exit 1

CMD ["python3", "alfred.py"]
