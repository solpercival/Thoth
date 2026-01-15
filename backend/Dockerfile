# Backend Dockerfile for Thoth Application
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    git \
    portaudio19-dev \
    libportaudio2 \
    espeak \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies with longer timeout for large packages like torch
# Split into two steps: basic deps first, then torch/heavy packages
RUN pip install --no-cache-dir \
    --default-timeout=3000 \
    --retries 10 \
    -r requirements.txt

# Copy backend code
COPY . .

# Expose port for the backend API
EXPOSE 5000

# Health check (simple, just check if port is open)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 5000), timeout=5)" || exit 1

# Start the backend
CMD ["python", "thoth/core/call_assistant/app_v3.py"]
