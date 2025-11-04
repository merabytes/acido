# acido &nbsp;🔥
[![GitHub release](https://img.shields.io/github/v/release/merabytes/acido?include_prereleases&color=blueviolet)](https://github.com/merabytes/acido/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/merabytes/acido/ci.yml?label=build&logo=github)](https://github.com/merabytes/acido/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Live Demo](https://img.shields.io/badge/docs-online-blue?logo=readthedocs)](https://secrets.merabytes.com)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat&logo=github)](https://github.com/merabytes/acido/pulls)
[![Twitter Follow](https://img.shields.io/twitter/follow/merabytes?style=social)](https://twitter.com/merabytes)


> **The open-source engine powering [Secrets by Merabytes™](https://secrets.merabytes.com)**  
> Disrupting how secrets, tokens, and one-time credentials are shared — forever.

acido isn’t just another CLI tool. It’s the backbone of an infrastructure-first rethink of how secrets, tokens and one-time credentials are built, deployed and consumed.

Already powering Secrets by Merabytes™ — the first truly open-source secret-sharing app — acido installs like a developer tool and scales like an enterprise service.

Deploy fleets of workloads on Azure Container Instances in minutes.

Leverage full transparency: open source, auditable, no lock-in.

Built for the next generation of identity, secrets and “one-time everything”.

Whether you’re building a secure secret-sharing system, a distributor of short-lived credentials, or simply pushing containerised tasks to the edge — acido gives you the power, the scale and the freedom of open source.

## Table of Contents

- [Why Acido?](#why-acido)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Examples](#examples)
- [Docker Usage](#docker-usage)
- [AWS Lambda Support](#aws-lambda-support)
- [GitHub Self-Hosted Runners](#github-self-hosted-runners)
- [Secrets Sharing Service](#secrets-sharing-service)
- [Credits](#credits)

## Why Acido?

**Speed**: Distribute scans across 10, 50, or 100+ containers. What takes 24 hours on one machine completes in minutes with parallelization.

**Cost-Effective**: Pay only when scanning. Spin up 100 containers for 30 minutes, then destroy them - no idle infrastructure costs.

**Tool Support**: Works with any containerized security tool (nmap, masscan, Nuclei, Nikto, gowitness, etc.).

**Simple**: Split targets automatically, deploy containers, collect results, cleanup - all automated.

```
+---------------------------+
| 1. Prepare targets file   |
|    urls.txt               |
+------------+--------------+
             |
             v
+---------------------------+
| 2. Configure (first time) |
|    acido configure        |
+------------+--------------+
             |
             v
+-----------------------------+
| 3. Create nuclei image      |
|    `acido create nuclei     |
|    --image projectdiscovery/|
|          nuclei:latest`     |
+------------+----------------+
             |
             v
+----------------------------------------------+
| 4. Run distributed scan fleet                |
|    ` acido fleet nuclei-scan                 |
|      -n 10                                   |
|      -im nuclei                              |
|      -t "nuclei -list input"                 |
|      -i urls.txt                             |
|      -o results                              |
|      --rm-when-done (optional auto cleanup)` |
+------------+---------------------------------+
             |
             v
+---------------------------+
| 5. View results           |
|    Open 'results' file    |
+------------+--------------+
             |
             v
+------------------------+
| 6. Cleanup acido fleet |-- Yes (auto --rm-when-done)
+------------------------+
             |
        No   v
+---------------------------+
| Manual cleanup            |
| `acido rm nuclei-scan`    |
+---------------------------+

(If --rm-when-done was used, skip manual cleanup.)
```

Inspired by [axiom](https://github.com/pry0cc/axiom).

## Installation

**Prerequisites:**
- Python 3.7+
- Azure account ([free tier](https://azure.microsoft.com/free/) works)

### Quick Setup in Azure Cloud Shell

1. **Open Azure Cloud Shell:**
   - Go to [Azure Portal](https://portal.azure.com) and click the Cloud Shell icon (>_)

2. **Run the install script:**
   ```bash
   curl -o install.sh https://raw.githubusercontent.com/merabytes/acido/main/install.sh
   chmod +x install.sh
   
   # Replace SUB_ID with your Azure Subscription ID
   ./install.sh \
     -s SUB_ID \
     -g acido-rg \
     -l eastus \
     -p acido \
     -a acidocr \
     -S acidostore123 \
     --show-secret \
     --emit-env-file acido.env \
     --create-rg
   ```

   This creates: Service Principal, ACR, Storage Account, blob container, and generates a complete environment file.

3. **Load environment and install:**
   ```bash
   source acido.env
   pip install acido
   ```

4. **You're ready!** All Azure credentials are configured via environment variables.

## Quick Start

1. **Create scanning image from GitHub:**
```bash
acido create https://github.com/projectdiscovery/nuclei
```

2. **Run distributed scan:**
```bash
echo -e "example.com\ntest.com" > targets.txt
acido fleet nuclei-scan -n 3 -im nuclei -t 'nuclei -list input' -i targets.txt
```

3. **Manage containers:**
```bash
acido ls              # List all instances
acido rm nuclei-scan  # Remove specific fleet
```

4. **Manage IP addresses:**
```bash
acido ip create pentest-ip   # Create IPv4 address
acido ip ls                  # List all IPs
acido ip rm pentest-ip       # Remove IP address
```

## CLI Reference

### Core Commands

```bash
# Create images
acido create https://github.com/projectdiscovery/nuclei
acido create nmap --image nmap:latest

# Deploy fleet
acido fleet <name> -n <count> -im <image> -t '<command>' -i <input-file>

# Manage containers
acido ls                    # List all instances
acido rm <name>             # Remove instances

# Manage IP addresses
acido ip create <name>      # Create IPv4 address
acido ip ls                 # List all IPs
acido ip rm <name>          # Remove IP
acido ip select             # Select IP interactively
```

## Examples

### Distributed Scanning

```bash
# Nuclei scan across 10 containers
acido fleet nuclei-scan -n 10 -im nuclei -t 'nuclei -list input' -i urls.txt

# Nmap scan with auto-cleanup
acido fleet nmap-scan -n 5 -im nmap -t 'nmap -iL input -p-' -i targets.txt --rm-when-done
```

### Container Management

```bash
# List all running instances
acido ls

# Remove specific fleet
acido rm nuclei-scan

# Remove all matching pattern
acido rm 'scan-*'
```

### IP Address Routing

```bash
# Create and use static IP
acido ip create pentest-ip
acido ip select

# Deploy with IP routing (containers use selected IP)
acido fleet scan -n 10 -im nmap -t 'nmap -iL input' -i targets.txt

# Cleanup
acido ip rm pentest-ip
```

## Docker Usage

Acido can be run in a Docker container for isolated and reproducible environments.

**Quick Start:**

Build the Docker image from the latest version:
```bash
./build.sh
```

Or from a specific branch/tag:
```bash
./build.sh v0.45.0
./build.sh feature-branch
```

**Run acido commands:**
```bash
# Show help
docker run --rm acido-cli:main --help

# Run with Azure credentials
docker run --rm \
  -e AZURE_RESOURCE_GROUP=your-rg \
  -e IMAGE_REGISTRY_SERVER=your-registry.azurecr.io \
  -e IMAGE_REGISTRY_USERNAME=your-username \
  -e IMAGE_REGISTRY_PASSWORD=your-password \
  -e STORAGE_ACCOUNT_NAME=your-storage \
  acido-cli:main ls
```

**Key Features:**
- Pre-built Docker image with acido CLI
- Isolated environment for testing
- Easy distribution and deployment
- Automated build script (`build.sh`)
- CI/CD tested in GitHub Actions

**Documentation:**
- See [DOCKER.md](DOCKER.md) for complete Docker usage guide
- Includes examples for mounting files and environment variables

## AWS Lambda Support

Acido can be deployed as an AWS Lambda function, enabling serverless security scanning workflows.

**Key Features:**
- Serverless invocation via AWS Lambda
- Automatic container provisioning in Azure
- JSON-based event interface
- Continuous deployment via GitHub Actions
- **New:** Full CRUD operations support (fleet, run, ls, rm, ip)

**Supported Operations:**

1. **Fleet Operation** - Distributed scanning across multiple containers:
```json
{
  "operation": "fleet",
  "image": "nmap",
  "targets": ["merabytes.com", "uber.com"],
  "task": "nmap -iL input -p 0-1000"
}
```

2. **Run Operation** - Single ephemeral instance:
```json
{
  "operation": "run",
  "name": "runner-01",
  "image": "ubuntu",
  "task": "./run.sh"
}
```

3. **List Operation** - List all container instances:
```json
{
  "operation": "ls"
}
```

4. **Remove Operation** - Remove container instances:
```json
{
  "operation": "rm",
  "name": "fleet-1"
}
```

5. **IP Management Operations** - Manage IPv4 addresses:
```json
{
  "operation": "ip_create",
  "name": "pentest-ip"
}
```
```json
{
  "operation": "ip_ls"
}
```
```json
{
  "operation": "ip_rm",
  "name": "pentest-ip"
}
```

**Quick Example:**
```json
{
  "image": "nmap",
  "targets": ["merabytes.com", "uber.com", "facebook.com"],
  "task": "nmap -iL input -p 0-1000"
}
```

**Documentation:**
- See [LAMBDA.md](LAMBDA.md) for complete deployment and usage instructions
- See [LAMBDA_API_EXAMPLES.md](LAMBDA_API_EXAMPLES.md) for detailed API usage examples and CLI equivalents
- Example payload: [examples/example_lambda_payload.json](examples/example_lambda_payload.json)
- Automatic deployment workflow: [.github/workflows/deploy-lambda.yml](.github/workflows/deploy-lambda.yml)

## GitHub Self-Hosted Runners

Acido supports spinning up ephemeral GitHub self-hosted runner containers on Azure Container Instances.

**Key Features:**
- Single ephemeral container instances with auto-cleanup
- Configurable duration (up to 15 minutes for Lambda compatibility)
- Ideal for on-demand CI/CD workers
- Cost-effective: pay only for runtime
- AWS Lambda orchestration support

**Quick Example:**

Run a GitHub runner for 15 minutes via CLI:
```bash
acido run github-runner-01 \
  -im github-runner \
  -t './run.sh --url https://github.com/myorg/myrepo --token TOKEN' \
  -d 900
```

Or via AWS Lambda:
```json
{
  "operation": "run",
  "name": "github-runner-01",
  "image": "github-runner",
  "task": "./run.sh --url https://github.com/myorg/myrepo --token ${RUNNER_TOKEN}",
  "duration": 900
}
```

**Documentation:**
- See [GITHUB_RUNNERS.md](GITHUB_RUNNERS.md) for complete setup and usage instructions
- Example payload: [examples/example_lambda_github_runner_payload.json](examples/example_lambda_github_runner_payload.json)

## Secrets Sharing Service

Acido includes a OneTimeSecret-like service for secure secrets sharing via AWS Lambda and Azure KeyVault.

**Key Features:**
- Generate UUID-based secrets
- One-time access (auto-delete after retrieval)
- Secure storage in Azure KeyVault
- Serverless AWS Lambda deployment
- Optional CloudFlare Turnstile bot protection

**Quick Example:**

Create a secret:
```json
{
  "action": "create",
  "secret": "Your secret message here"
}
```

Retrieve the secret (one-time only):
```json
{
  "action": "retrieve",
  "uuid": "generated-uuid-from-create"
}
```

**Documentation:**
- See [SECRETS.md](SECRETS.md) for complete documentation
- Example payloads: [examples/example_lambda_secrets_create_payload.json](examples/example_lambda_secrets_create_payload.json) and [examples/example_lambda_secrets_retrieve_payload.json](examples/example_lambda_secrets_retrieve_payload.json)
- Automatic deployment workflow: [.github/workflows/deploy-lambda-secrets.yml](.github/workflows/deploy-lambda-secrets.yml)

## Credits

* Xavier Álvarez (xalvarez@merabytes.com)
* Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)
