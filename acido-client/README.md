# acido-client

REST API client for interacting with acido Lambda functions.

## Installation

```bash
pip install acido-client
```

## Usage

The client expects the `LAMBDA_FUNCTION_URL` environment variable to be set with the URL of your acido Lambda function.

```bash
export LAMBDA_FUNCTION_URL="https://your-lambda-url.lambda-url.region.on.aws/"
```

### Python API

```python
from acido_client import AcidoClient

# Initialize client (uses LAMBDA_FUNCTION_URL from environment)
client = AcidoClient()

# Or specify URL explicitly
client = AcidoClient(lambda_url="https://your-lambda-url.lambda-url.region.on.aws/")

# Fleet operation - distributed scanning
response = client.fleet(
    image="kali-rolling",
    targets=["merabytes.com", "uber.com"],
    task="nmap -iL input -p 0-1000",
    region="westeurope"
)

# Run operation - single ephemeral instance
response = client.run(
    name="github-runner-01",
    image="github-runner",
    task="./run.sh",
    duration=900,
    cleanup=True,
    region="westeurope"
)

# List container instances
response = client.ls()

# Remove container instances
response = client.rm(name="fleet*")

# Create IPv4 address
response = client.ip_create(name="pentest-ip")

# List IPv4 addresses
response = client.ip_ls()

# Remove IPv4 address
response = client.ip_rm(name="pentest-ip")
```

### Command Line Interface

```bash
# Fleet operation
acido-client fleet --image kali-rolling --targets merabytes.com uber.com --task "nmap -iL input -p 0-1000"

# Run operation
acido-client run --name github-runner-01 --image github-runner --task "./run.sh" --duration 900

# List container instances
acido-client ls

# Remove container instances
acido-client rm --name "fleet*"

# Create IPv4 address
acido-client ip-create --name pentest-ip

# List IPv4 addresses
acido-client ip-ls

# Remove IPv4 address
acido-client ip-rm --name pentest-ip
```

## Supported Operations

- **fleet**: Deploy multiple container instances for distributed scanning
- **run**: Deploy single ephemeral instance with auto-cleanup
- **ls**: List all container instances
- **rm**: Remove container instances (supports wildcards)
- **ip_create**: Create IPv4 address and network profile
- **ip_ls**: List all IPv4 addresses
- **ip_rm**: Remove IPv4 address and network profile

## Features

- **Lightweight**: Minimal dependencies (only `requests`)
- **Independent**: Completely independent from the main acido package
- **Complete**: Supports all 7 Lambda operations
- **Easy to use**: Simple Python API and CLI
- **Context manager support**: Can be used with Python's `with` statement

## Requirements

- Python 3.7 or higher
- requests >= 2.25.0

## Examples

See the [examples](examples/) directory for more usage examples.

## Development

To install in development mode:

```bash
cd acido-client
pip install -e .
```

To run tests:

```bash
cd acido-client
pip install pytest pytest-cov
pytest tests/ -v
```

## License

MIT
