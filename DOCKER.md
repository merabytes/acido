# Docker Usage Guide

This guide explains how to use acido with Docker.

## Quick Start

### Using Pre-built Image

Build the acido CLI image from the latest main branch:

```bash
./build.sh
```

Or from a specific branch/tag:

```bash
./build.sh v0.44.0
./build.sh feature-branch
```

### Running acido Commands

Once built, you can run acido commands using Docker:

```bash
# Show help
docker run --rm acido-cli:main --help

# Show subcommand help
docker run --rm acido-cli:main create --help
docker run --rm acido-cli:main fleet --help
docker run --rm acido-cli:main ip --help
```

### Using with Environment Variables

Pass Azure credentials and configuration via environment variables:

```bash
docker run --rm \
  -e AZURE_RESOURCE_GROUP=your-rg \
  -e IMAGE_REGISTRY_SERVER=your-registry.azurecr.io \
  -e IMAGE_REGISTRY_USERNAME=your-username \
  -e IMAGE_REGISTRY_PASSWORD=your-password \
  -e STORAGE_ACCOUNT_NAME=your-storage \
  acido-cli:main ls
```

### Mounting Files

Mount local directories to access input files:

```bash
docker run --rm \
  -v $(pwd)/targets.txt:/data/targets.txt \
  -e AZURE_RESOURCE_GROUP=your-rg \
  -e IMAGE_REGISTRY_SERVER=your-registry.azurecr.io \
  -e IMAGE_REGISTRY_USERNAME=your-username \
  -e IMAGE_REGISTRY_PASSWORD=your-password \
  -e STORAGE_ACCOUNT_NAME=your-storage \
  acido-cli:main fleet scan-fleet -n 5 -im nmap -t 'nmap -iL input' -i /data/targets.txt
```

## Dockerfile

The included `Dockerfile` creates a lightweight image with:
- Python 3.12 slim base
- Required system dependencies (git, build tools)
- acido installed and ready to use
- `acido` set as the entrypoint

## Build Script

The `build.sh` script automates building the Docker image from the GitHub repository:

```bash
#!/bin/bash
# Builds acido Docker image from a specific branch/tag

./build.sh [branch|tag|commit]
```

**Examples:**
```bash
./build.sh main           # Build from main branch
./build.sh v0.44.0        # Build from a specific release
./build.sh feature-x      # Build from a feature branch
```

The script:
1. Clones the specified branch from GitHub
2. Builds the Docker image with tag `acido-cli:<branch>`
3. Cleans up temporary files

## CI/CD Integration

The Docker build is automatically tested in GitHub Actions CI. See `.github/workflows/ci.yml` for the `docker-build-test` job which:
- Builds the Docker image
- Tests all CLI commands
- Verifies environment variable support

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate errors during build, this is typically a local environment issue. The image will build successfully in GitHub Actions CI.

### Permission Denied

Make sure `build.sh` is executable:
```bash
chmod +x build.sh
```

### Docker Daemon Not Running

Ensure Docker is installed and running:
```bash
docker --version
docker ps
```
