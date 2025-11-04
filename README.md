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
- Docker
- Azure account ([free tier](https://azure.microsoft.com/free/) works)

### Option 1: Quick Setup in Azure Cloud Shell (Recommended)

The easiest way to set up acido is using the automated install script in Azure Cloud Shell. This script creates all required Azure resources with a single command.

1. **Open Azure Cloud Shell:**
   - Go to [Azure Portal](https://portal.azure.com)
   - Click the Cloud Shell icon (>_) in the top navigation bar
   - Choose Bash when prompted

2. **Upload and run the install script:**
   ```bash
   # Download the install script
   curl -o install.sh https://raw.githubusercontent.com/merabytes/acido/main/install.sh
   chmod +x install.sh
   
   # Run the script with your preferred configuration
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

   **What this creates:**
   - Service Principal with appropriate permissions
   - Azure Container Registry (ACR) for Docker images
   - Storage Account with blob container for input/output files
   - User Assigned Managed Identity (optional)
   - Key Vault (optional with `-k` flag)

3. **Load environment variables:**
   ```bash
   source acido.env
   ```

4. **Install acido:**
   ```bash
   pip install acido
   ```

5. **You're ready!** Skip the `az login` step - the environment variables are already configured.

**Advanced options:**
```bash
# Least privilege mode (granular permissions instead of Contributor)
./install.sh -s SUB -g acido-rg -l eastus -p acido -a acidocr -S acidostore \
  --least-privilege --identity-name acido-id --emit-env-file acido.env

# Include Key Vault for secrets management
./install.sh -s SUB -g acido-rg -l eastus -p acido -S acidostore \
  -k acidokv --kv-secret STORAGE_CONN="your-connection-string" --emit-env-file acido.env
```

For complete install.sh options, run: `./install.sh --help`

### Option 2: Manual Setup

**Setup:**

1. Install acido:
```bash
pip install acido
```

2. Login to Azure:
```bash
az login
```

3. Create Azure Container Registry:
```bash
az acr create --resource-group MyResourceGroup --name myregistry --sku Basic
```

4. Configure acido:
```bash
acido -c
# or
acido configure
```
Provide: resource group name, registry server (e.g., `myregistry.azurecr.io`), registry username, registry password, and storage account name.

**Note:** For CI/CD pipelines and Lambda deployments, you can use environment variables instead:
- `AZURE_RESOURCE_GROUP`
- `IMAGE_REGISTRY_SERVER`
- `IMAGE_REGISTRY_USERNAME`
- `IMAGE_REGISTRY_PASSWORD`
- `STORAGE_ACCOUNT_NAME`
- `STORAGE_ACCOUNT_KEY` (optional, if not provided will fetch from Azure)

See [.github/AZURE_PERMISSIONS.md](.github/AZURE_PERMISSIONS.md) for detailed Service Principal setup and permissions.

## Quick Start

1. Create a target list (`targets.txt`):
```
facebook.com
uber.com
paypal.com
```

2. Create scanning image:
```bash
# Using short name (will look for 'nmap' image)
acido create nmap

# Or specify the full Docker image URL
acido create nuclei --image projectdiscovery/nuclei:latest

# For images that run as non-root user (e.g., alpine/nikto)
acido create nikto --image alpine/nikto:latest --root

# Install additional packages during image creation
acido create nikto --image alpine/nikto:latest --root --install python3 --install nmap

# Or build from a GitHub repository (must contain a Dockerfile)
acido create git+https://github.com/user/custom-scanner

# With specific branch or tag
acido create git+https://github.com/user/custom-scanner@main
acido create git+https://github.com/user/custom-scanner@v1.0.0
```

3. Run distributed scan (Docker-like syntax):
```bash
acido fleet nmap-scan \
    -n 3 \
    -im nmap \
    -t 'nmap -iL input -p 0-1000' \
    -i targets.txt \
    -o output \
    --rm-when-done
```

Or using the classic syntax (still supported):
```bash
acido -f nmap-scan \
    -n 3 \
    -im nmap \
    -t 'nmap -iL input -p 0-1000' \
    -i targets.txt \
    -o output \
    --rm-when-done
```

Parameters:
- `fleet` / `-f` Fleet name
- `-n` Number of container instances
- `-im` Image name (e.g., 'nmap', 'nuclei:latest', or full URL)
- `-t` Command to execute
- `-i` Input file (auto-split across containers)
- `-o` Output file
- `--rm-when-done` Auto-delete containers after completion

Results saved to `output.json` and `all_output.txt`.

## CLI Reference

Acido now supports Docker-like subcommands for a more intuitive experience:

### Subcommands

```bash
# Create acido-compatible image from base Docker image
acido create <name> [--image <full-image-url>] [--root] [--install <package>] [--no-update]

# Create acido-compatible image from GitHub repository (must contain Dockerfile)
acido create git+https://github.com/user/repo[@ref]

# Configure acido
acido configure

# Deploy a fleet of containers
acido fleet <fleet-name> [options]

# Run a single ephemeral container with auto-cleanup
acido run <name> [options]

# List all container instances
acido ls

# Remove container instances
acido rm <name-or-pattern>

# IP address management
acido ip create <name>    # Create IPv4 address and network profile
acido ip ls               # List all IPv4 addresses
acido ip rm <name>        # Remove IPv4 address and network profile
acido ip select           # Select an IPv4 address to use

# Select instances by pattern
acido select <pattern>

# Execute command on selected instances  
acido exec <command> [options]
```

### Create Command Options

```bash
acido create <name> [options]

Options:
  --image IMAGE_URL           Full Docker image URL (e.g., 'projectdiscovery/nuclei:latest')
  --install PACKAGE           Install additional package (can be used multiple times)
  --no-update                 Skip package list update before installing packages
  --root                      Run as root user (for images that default to non-root)
  --use-venv                  Use Python virtual environment (larger image, more flexible)
  --break-system-packages     [Deprecated] Use --use-venv instead (kept for compatibility)
  --entrypoint ENTRYPOINT     Override default ENTRYPOINT (e.g., "/bin/bash")
  --cmd CMD                   Override default CMD (e.g., "sleep infinity")

Examples:
  # Create from base image (uses pre-built binary - lightweight)
  acido create nmap --image nmap:latest
  
  # Create with root privileges (for non-root images like alpine/nikto)
  acido create nikto --image alpine/nikto:latest --root
  
  # Install additional packages
  acido create custom --image alpine:latest --root --install python3 --install nmap
  
  # Create nuclei image with pre-built binary (default, lightweight)
  acido create nuclei --image projectdiscovery/nuclei:latest
  
  # Create nuclei image with virtual environment (larger but more flexible)
  acido create nuclei --image projectdiscovery/nuclei:latest --use-venv
  
  # Custom entrypoint and command
  acido create ubuntu --image ubuntu:20.04 --entrypoint "/bin/bash" --cmd "echo hello"
  
  # Build from GitHub repository
  acido create git+https://github.com/user/repo@main
```

### Fleet Command Options

```bash
acido fleet <fleet-name> [options]

Options:
  -n, --num-instances NUM   Number of container instances
  -im, --image IMAGE        Image name (e.g., 'nmap', 'nuclei:latest')
  -t, --task TASK          Command to execute
  -i, --input-file FILE    Input file (auto-split across containers)
  -w, --wait SECONDS       Max timeout in seconds
  -o, --output FILE        Save output to file
  --format FORMAT          Output format: txt or json (default: txt)
  -q, --quiet              Quiet mode with progress bar
  --rm-when-done          Remove containers after completion
```

### Legacy Flags (Still Supported)

For backward compatibility, all original flags are still supported:

```
usage: acido [-h] [-c] [-f FLEET] [-im IMAGE_NAME] [--create-ip CREATE_IP] 
             [--ip] [-n NUM_INSTANCES] [-t TASK] [-e EXEC_CMD] 
             [-i INPUT_FILE] [-w WAIT] [-s SELECT] [-l] [-r REMOVE] [-in]
             [-sh SHELL] [-d DOWNLOAD_INPUT] [-o WRITE_TO_FILE] [-rwd]
             {create,configure,fleet,ls,rm,select,exec}

positional arguments:
  {create,configure,fleet,ls,rm,select,exec}
                        Subcommands

optional arguments:
  -h, --help            Show help message
  -c, --config          Configure acido
  -f FLEET              Fleet name (deprecated: use 'acido fleet' subcommand)
  -im IMAGE_NAME        Deploy specific image
  --create IMAGE        Create acido-compatible image (alternative syntax)
  --create-ip NAME      Create IPv4 address for routing
  --ip                  Use existing IPv4 address
  -n NUM                Number of instances
  -t TASK               Command to execute
  -e EXEC_CMD           Execute on selected instances
  -i INPUT_FILE         Input file for task
  -w WAIT               Max timeout
  -s SELECT             Select instances by name/regex
  -l, --list            List all instances (deprecated: use 'acido ls')
  -r REMOVE             Remove instances by name/regex (deprecated: use 'acido rm')
  -in, --interactive    Interactive session
  -sh SHELL             Execute and upload to blob
  -d DOWNLOAD           Download from blob
  -o OUTPUT             Save output in JSON
  -rwd, --rm-when-done  Remove containers after completion
```


## Examples

### Distributed Nmap Scan

Scan 1,000 hosts with 20 containers using new Docker-like syntax:

```bash
acido fleet nmap-fleet \
    -n 20 \
    -im nmap \
    -t 'nmap -iL input -p- --min-rate 1000' \
    -i targets.txt \
    -o output \
    --rm-when-done
```

Or using classic syntax:
```bash
acido -f nmap-fleet \
    -n 20 \
    -im nmap \
    -t 'nmap -iL input -p- --min-rate 1000' \
    -i targets.txt \
    -o output \
    --rm-when-done
```

### Nuclei Vulnerability Scan

Scan 10,000 URLs with 50 containers:

```bash
acido fleet nuclei-scan \
    -n 50 \
    -im nuclei \
    -t 'nuclei -list input -t /nuclei-templates/' \
    -i urls.txt \
    -o results
```

### Masscan Port Discovery

Scan entire network with 100 containers:

```bash
acido fleet masscan \
    -n 100 \
    -im masscan \
    -t 'masscan -iL input -p0-65535 --rate 10000' \
    -i networks.txt \
    -o masscan-results
```

### Fleet Management

List all running container instances:
```bash
acido ls
```

Remove specific fleet:
```bash
acido rm nmap-fleet
```

Remove all fleets matching pattern:
```bash
acido rm 'scan-*'
```

### Building from GitHub

Build custom acido-compatible images directly from GitHub repositories containing Dockerfiles:

```bash
# Build from main branch
acido create git+https://github.com/myorg/custom-scanner

# Build from specific branch
acido create git+https://github.com/myorg/custom-scanner@develop

# Build from specific tag
acido create git+https://github.com/myorg/custom-scanner@v2.1.0

# Build from specific commit
acido create git+https://github.com/myorg/custom-scanner@abc123def456
```

**Requirements:**
- Repository must contain a `Dockerfile` at the root
- Git must be installed locally
- Image will be built and pushed to your Azure Container Registry

**Example workflow:**
1. Create a GitHub repository with your custom Dockerfile
2. Build the image: `acido create git+https://github.com/myorg/scanner@v1.0`
3. Use the image: `acido fleet scan -n 10 -im scanner-acido:v1-0 -t 'your-command'`

**Note:** The `--install` option is not supported for GitHub URLs since the Dockerfile defines all dependencies.

### Single IP Routing

Route all containers through one IP for whitelisting:

```bash
# Create IP address and network profile
acido ip create pentest-ip

# List all IPv4 addresses
acido ip ls

# Select IP address interactively
acido ip select

# Deploy with IP routing
acido fleet scan -n 50 \
    -im nmap \
    -t 'nmap -iL input -p-' \
    -i targets.txt

# Remove IP address when done
acido ip rm pentest-ip
```

**Note:** The old syntax (`acido --create-ip <name>` and `acido --ip`) is still supported for backward compatibility.

## Docker Usage

Acido can be run in a Docker container for isolated and reproducible environments.

**Quick Start:**

Build the Docker image from the latest version:
```bash
./build.sh
```

Or from a specific branch/tag:
```bash
./build.sh v0.44.0
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
