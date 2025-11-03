#!/bin/bash
# build.sh - Build acido Docker image from GitHub repository
#
# Usage:
#   ./build.sh [branch|tag|commit]
#
# Examples:
#   ./build.sh main
#   ./build.sh v0.44.0
#   ./build.sh feature-branch
#
# This script builds the acido CLI Docker image from a specific branch/tag/commit
# of the GitHub repository.

set -e

# Default to main branch if no argument provided
BRANCH="${1:-main}"

echo "=============================================="
echo "Building acido Docker image from GitHub"
echo "Repository: github.com/merabytes/acido"
echo "Branch/Tag: $BRANCH"
echo "=============================================="

# Create a temporary directory
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Clone the repository
echo "Cloning repository..."
git clone --depth 1 --branch "$BRANCH" https://github.com/merabytes/acido.git "$TEMP_DIR"

# Build the Docker image
echo "Building Docker image..."
cd "$TEMP_DIR"
docker build -t "acido-cli:${BRANCH}" -f Dockerfile .

# Clean up
echo "Cleaning up temporary directory..."
rm -rf "$TEMP_DIR"

echo "=============================================="
echo "Build completed successfully!"
echo "Image name: acido-cli:${BRANCH}"
echo ""
echo "Usage examples:"
echo "  docker run --rm acido-cli:${BRANCH} --help"
echo "  docker run --rm acido-cli:${BRANCH} create --help"
echo "  docker run --rm acido-cli:${BRANCH} fleet --help"
echo "=============================================="
