# GitHub Self-Hosted Runners with Acido

This guide explains how to use acido to spin up GitHub self-hosted runner containers on Azure Container Instances.

## Overview

Acido now supports running ephemeral single-instance containers with auto-cleanup, making it ideal for:
- **GitHub self-hosted runners** that run for a specific duration
- **Temporary CI/CD workers** for specific jobs
- **Time-limited workloads** that need automatic cleanup
- **AWS Lambda-based orchestration** (supports up to 15 minutes)

## Quick Start

### 1. Create a GitHub Runner Image

First, create an acido-compatible image based on the official GitHub runner:

```bash
# Create a Dockerfile for GitHub runner
cat > Dockerfile.github-runner << 'EOF'
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Download and extract GitHub Actions Runner
# Note: Check https://github.com/actions/runner/releases for the latest version
ARG RUNNER_VERSION="2.311.0"
WORKDIR /actions-runner
RUN curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
    && tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
    && rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Install acido wrapper script
RUN apt-get update && apt-get install -y python3 python3-pip
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# Set working directory
WORKDIR /actions-runner

# Default command (will be overridden by acido)
CMD ["sleep", "infinity"]
EOF

# Build and push to your registry using acido
acido create github-runner --image ubuntu:22.04
```

### 2. Run a GitHub Runner Instance

#### Using CLI

Run a single GitHub runner for 15 minutes (900 seconds):

```bash
acido run github-runner-01 \
  -im github-runner \
  -t './run.sh --url https://github.com/myorg/myrepo --token YOUR_TOKEN' \
  -d 900 \
  --quiet
```

Parameters:
- `github-runner-01`: Container instance name
- `-im github-runner`: Image name from step 1
- `-t`: Command to execute (configure and start the runner)
- `-d 900`: Duration in seconds (default: 900s/15min, max: 900s)
- `--quiet`: Quiet mode with progress bar
- `--no-cleanup`: Skip auto-cleanup (optional, for debugging)

#### Using AWS Lambda

Deploy a Lambda function that can spin up GitHub runners on demand:

**Example Lambda payload:**

```json
{
  "operation": "run",
  "name": "github-runner-01",
  "image": "github-runner",
  "task": "./run.sh --url https://github.com/myorg/myrepo --token ${RUNNER_TOKEN}",
  "duration": 900,
  "cleanup": true
}
```

**Invoke via AWS CLI:**

```bash
aws lambda invoke \
  --function-name Acido \
  --payload file://examples/example_lambda_github_runner_payload.json \
  response.json
```

**Environment variables required:**

Set these as Lambda environment variables:
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_RESOURCE_GROUP`
- `IMAGE_REGISTRY_SERVER`
- `IMAGE_REGISTRY_USERNAME`
- `IMAGE_REGISTRY_PASSWORD`
- `STORAGE_ACCOUNT_NAME`
- `RUNNER_TOKEN` (GitHub runner registration token)

### 3. Automation with GitHub Actions

You can automate runner creation from GitHub Actions workflows:

```yaml
name: Trigger Self-Hosted Runner

on:
  workflow_dispatch:

jobs:
  trigger-runner:
    runs-on: ubuntu-latest
    steps:
      - name: Generate runner token
        id: runner-token
        run: |
          # Use GitHub API to generate a runner registration token
          TOKEN=$(curl -X POST \
            -H "Authorization: token ${{ secrets.GITHUB_TOKEN }}" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/${{ github.repository }}/actions/runners/registration-token \
            | jq -r .token)
          echo "::set-output name=token::$TOKEN"
      
      - name: Invoke Lambda to spin up runner
        run: |
          aws lambda invoke \
            --function-name Acido \
            --payload "{\"operation\":\"run\",\"name\":\"github-runner-${{ github.run_id }}\",\"image\":\"github-runner\",\"task\":\"./run.sh --url https://github.com/${{ github.repository }} --token ${{ steps.runner-token.outputs.token }}\",\"duration\":900}" \
            response.json
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: us-east-1
```

## Architecture

```
GitHub Workflow
      ↓
  AWS Lambda (Acido)
      ↓
Azure Container Instance
      ↓
GitHub Runner Agent
      ↓
Execute Job
      ↓
Auto-Cleanup (after 15min)
```

## Use Cases

### 1. On-Demand CI/CD Workers

Spin up runners only when needed, reducing costs:

```bash
# Start a runner for a specific duration
acido run ci-worker-01 \
  -im github-runner \
  -t './run.sh --url https://github.com/myorg/myrepo --token TOKEN' \
  -d 600  # 10 minutes
```

### 2. Lambda-Based Orchestration

Use AWS Lambda to orchestrate runner creation with up to 15 minutes of execution time:

- Lambda timeout: 15 minutes (max)
- Container duration: up to 900 seconds (15 minutes)
- Auto-cleanup happens within Lambda execution

### 3. Parallel Job Execution

Run multiple ephemeral runners for parallel jobs:

```bash
# Spin up 3 runners in parallel
for i in {1..3}; do
  acido run github-runner-$i \
    -im github-runner \
    -t "./run.sh --url https://github.com/myorg/myrepo --token TOKEN" \
    -d 900 &
done
wait
```

## Configuration Options

### `run` Command Options

```
acido run <name> [options]

Options:
  -im, --image IMAGE       Image name (e.g., 'github-runner')
  -t, --task TASK         Command to execute
  -d, --duration SECONDS  Duration before auto-cleanup (default: 900, max: 900)
  -o, --output FILE       Save output to file
  --format FORMAT         Output format: txt or json (default: txt)
  -q, --quiet            Quiet mode with progress bar
  --no-cleanup           Skip auto-cleanup (for debugging)
```

### Lambda Payload Options

```json
{
  "operation": "run",
  "name": "container-name",
  "image": "image-name",
  "task": "command-to-execute",
  "duration": 900,        // optional, default 900s
  "cleanup": true         // optional, default true
}
```

## Security Considerations

1. **Token Management**: Never hardcode GitHub runner tokens. Use environment variables or secrets management:
   ```bash
   export RUNNER_TOKEN=$(gh api repos/owner/repo/actions/runners/registration-token --jq .token)
   ```

2. **Container Isolation**: Each runner runs in an isolated Azure Container Instance with its own network and resources.

3. **Auto-Cleanup**: Containers are automatically deleted after the specified duration to prevent resource leaks and reduce costs.

4. **Access Control**: Use Azure RBAC and Managed Identities to control who can create container instances.

## Troubleshooting

### Runner Not Connecting

Check container logs:
```bash
acido ls  # Find the container name
# View logs using Azure Portal or Azure CLI
az container logs --resource-group YOUR_RG --name github-runner-01
```

### Duration Too Short

Increase the duration parameter:
```bash
acido run github-runner-01 \
  -im github-runner \
  -t './run.sh --url URL --token TOKEN' \
  -d 900  # Max 15 minutes for Lambda compatibility
```

### Container Not Cleaning Up

Check if `--no-cleanup` was used. If cleanup is failing, manually remove:
```bash
acido rm github-runner-01
```

## Cost Optimization

- **Pay-per-use**: Only pay for container runtime (duration of the job)
- **Auto-cleanup**: Containers are automatically deleted after duration expires
- **No idle costs**: Unlike persistent runners, no cost when not in use
- **Flexible sizing**: Choose container size based on job requirements

## Limitations

- **Maximum duration**: 900 seconds (15 minutes) for Lambda compatibility
- **Single instance**: `run` command creates only one container instance
- **No input file splitting**: Unlike `fleet`, `run` doesn't support input file distribution
- **Lambda timeout**: AWS Lambda has a 15-minute maximum execution time

## Comparison: `run` vs `fleet`

| Feature | `run` | `fleet` |
|---------|-------|---------|
| Instances | Single | Multiple |
| Use Case | Ephemeral workers | Distributed scanning |
| Input Splitting | No | Yes |
| Auto-Cleanup | Built-in with duration | Optional with `--rm-when-done` |
| Duration Limit | 900s (15min) | No limit |
| Lambda Compatible | Yes | Yes (for short jobs) |

## Examples

See [examples/example_lambda_github_runner_payload.json](examples/example_lambda_github_runner_payload.json) for a complete Lambda payload example.

## Contributing

Found a bug or have a feature request? Open an issue on [GitHub](https://github.com/merabytes/acido/issues).
