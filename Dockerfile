# Sample Dockerfile for testing acido CLI
# This image contains the acido CLI tool ready to use

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the acido package
COPY . /app

# Install acido
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Verify installation
RUN acido --help

# Set acido as the entrypoint
ENTRYPOINT ["acido"]

# Default command (show help)
CMD ["--help"]
