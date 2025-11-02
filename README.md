# acido

**Distributed security scanning framework for Azure Container Instances.**

Acido (**A**zure **C**ontainer **I**nstance **D**istributed **O**perations) enables bug bounty hunters, penetration testers, and red team operators to scan at massive scale by distributing workloads across multiple Azure containers.

## Table of Contents

- [Why Acido?](#why-acido)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Examples](#examples)
- [AWS Lambda Support](#aws-lambda-support)
- [Credits](#credits)

## Why Acido?

**Speed**: Distribute scans across 10, 50, or 100+ containers. What takes 24 hours on one machine completes in minutes with parallelization.

**Cost-Effective**: Pay only when scanning. Spin up 100 containers for 30 minutes, then destroy them - no idle infrastructure costs.

**Tool Support**: Works with any containerized security tool (nmap, masscan, Nuclei, Nikto, gowitness, etc.).

**Simple**: Split targets automatically, deploy containers, collect results, cleanup - all automated.

![acido](https://user-images.githubusercontent.com/15344287/170670823-1e3b0de3-2834-4d38-a21d-368c50f073d3.png)

Inspired by [axiom](https://github.com/pry0cc/axiom).

## Installation

**Prerequisites:**
- Python 3.7+
- Docker
- Azure account ([free tier](https://azure.microsoft.com/free/) works)

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
```
Provide: resource group name, registry server (e.g., `myregistry.azurecr.io`), registry username, registry password, and storage account name.

**Note:** For CI/CD pipelines, see [.github/AZURE_PERMISSIONS.md](.github/AZURE_PERMISSIONS.md) for Service Principal setup.

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
```

3. Run distributed scan:
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
- `-f` Fleet name
- `-n` Number of container instances
- `-im` Image name (e.g., 'nmap', 'nuclei:latest', or full URL)
- `-t` Command to execute
- `-i` Input file (auto-split across containers)
- `-o` Output file
- `--rm-when-done` Auto-delete containers after completion

Results saved to `output.json` and `all_output.txt`.

## CLI Reference

```
usage: acido [-h] [-c] [-f FLEET] [-im IMAGE_NAME] [--create-ip CREATE_IP] 
             [--ip] [-n NUM_INSTANCES] [-t TASK] [-e EXEC_CMD] 
             [-i INPUT_FILE] [-w WAIT] [-s SELECT] [-l] [-r REMOVE] [-in]
             [-sh SHELL] [-d DOWNLOAD_INPUT] [-o WRITE_TO_FILE] [-rwd]
             {create}

positional arguments:
  {create}              Subcommands
    create              Create acido-compatible image from base image
                        Usage: acido create <name> [--image <full-image-url>]

optional arguments:
  -h, --help            Show help message
  -c, --config          Configure acido
  -f FLEET              Fleet name
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
  -l, --list            List all instances
  -r REMOVE             Remove instances by name/regex
  -in, --interactive    Interactive session
  -sh SHELL             Execute and upload to blob
  -d DOWNLOAD           Download from blob
  -o OUTPUT             Save output in JSON
  -rwd, --rm-when-done  Remove containers after completion
```


## Examples

### Distributed Nmap Scan

Scan 1,000 hosts with 20 containers:

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
acido -f nuclei-scan \
    -n 50 \
    -im nuclei \
    -t 'nuclei -list input -t /nuclei-templates/' \
    -i urls.txt \
    -o results
```

### Masscan Port Discovery

Scan entire network with 100 containers:

```bash
acido -f masscan \
    -n 100 \
    -im masscan \
    -t 'masscan -iL input -p0-65535 --rate 10000' \
    -i networks.txt \
    -o masscan-results
```

### Single IP Routing

Route all containers through one IP for whitelisting:

```bash
# Create IP
acido --create-ip pentest-ip

# Deploy with IP routing
acido -f scan -n 50 --ip \
    --image myregistry.azurecr.io/nmap:latest \
    -t 'nmap -iL input -p-' \
    -i targets.txt
```

## AWS Lambda Support

Acido can be deployed as an AWS Lambda function, enabling serverless security scanning workflows.

**Key Features:**
- Serverless invocation via AWS Lambda
- Automatic container provisioning in Azure
- JSON-based event interface
- Continuous deployment via GitHub Actions

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
- Example payload: [example_lambda_payload.json](example_lambda_payload.json)
- Automatic deployment workflow: [.github/workflows/deploy-lambda.yml](.github/workflows/deploy-lambda.yml)

## Credits

* Xavier Álvarez (xalvarez@merabytes.com)
* Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)
