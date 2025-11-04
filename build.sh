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

# Default to main branch if no argument provided
BRANCH="$(git branch --show-current)"

echo "=============================================="
echo "Building acido Docker image from GitHub"
echo "Repository: github.com/merabytes/acido"
echo "Branch/Tag: $BRANCH"
echo "=============================================="

# Create a temporary directory
git pull

# Build the Docker image
echo "Building Docker image..."
docker build . -t "acido:latest"

# Clean up
echo "Cleaning up temporary directory..."
rm -rf "$TEMP_DIR"

echo "=============================================="
echo "Build completed successfully!"
echo "Image name: acido-cli:${BRANCH}"
echo ""
echo "Usage examples:"
echo "  docker run --rm acido --help"
echo "  docker run --rm acido create --help"
echo "  docker run --rm acido fleet --help"
echo "=============================================="
