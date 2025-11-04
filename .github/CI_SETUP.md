# GitHub Actions CI Setup

This document explains how to configure the required environment variables for the CI/CD pipeline.

> **Note:** For detailed information about Azure permissions and creating a Service Principal, see [AZURE_PERMISSIONS.md](AZURE_PERMISSIONS.md).

## Required GitHub Secrets

To run the full integration tests with Azure, you need to configure the following secrets in your GitHub repository:

### Setting up GitHub Secrets

1. Go to your repository on GitHub
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each of the following:

### Azure Credentials (for CI Tests)

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `AZURE_RESOURCE_GROUP` | The Azure Resource Group name where ACIs will be deployed | `Merabytes` |
| `AZURE_REGISTRY_SERVER` | The Azure Container Registry server URL | `merabytes.azurecr.io` |
| `AZURE_REGISTRY_USERNAME` | The username for the Azure Container Registry | `merabytes` |
| `AZURE_REGISTRY_PASSWORD` | The password for the Azure Container Registry | `<your-registry-password>` |

### Optional: Azure Service Principal (for full Azure integration)

For full Azure integration tests, you can also configure:

| Secret Name | Description |
|------------|-------------|
| `AZURE_CLIENT_ID` | Azure Service Principal Client ID (for CI tests) |
| `AZURE_CLIENT_SECRET` | Azure Service Principal Client Secret (for CI tests) |
| `AZURE_TENANT_ID` | Azure Tenant ID (for CI tests) |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID |

### Lambda Deployment Credentials (CD Pipeline)

For Lambda deployments, use **separate** Service Principals for each Lambda function:

#### Main Lambda (Container Management)
| Secret Name | Description |
|------------|-------------|
| `LAMBDA_AZURE_TENANT_ID` | Azure Tenant ID for main Lambda |
| `LAMBDA_AZURE_CLIENT_ID` | Service Principal Client ID for main Lambda |
| `LAMBDA_AZURE_CLIENT_SECRET` | Service Principal Client Secret for main Lambda |

#### Secrets Lambda (Key Vault Access)
| Secret Name | Description |
|------------|-------------|
| `SECRETS_AZURE_TENANT_ID` | Azure Tenant ID for Secrets Lambda |
| `SECRETS_AZURE_CLIENT_ID` | Service Principal Client ID for Secrets Lambda |
| `SECRETS_AZURE_CLIENT_SECRET` | Service Principal Client Secret for Secrets Lambda |
| `KEY_VAULT_NAME` | Azure Key Vault name for secrets storage |

**Security Best Practice:** The separation of credentials ensures:
- Main Lambda SP has container/network permissions, no Key Vault access
- Secrets Lambda SP has only Key Vault access, no container permissions
- Principle of least privilege applied to both identities

**See [AZURE_PERMISSIONS.md](AZURE_PERMISSIONS.md) for detailed instructions on creating separate Service Principals with the correct permissions.**

## CI Workflow Overview

The CI workflow includes the following jobs:

### 1. Test Job
- Runs on Python 3.8, 3.9, 3.10, 3.11, and 3.12
- Installs dependencies
- Verifies acido installation
- Tests all module imports
- Runs CLI help command
- Performs Python syntax checks

### 2. Build Test Job
- Builds the distribution package
- Installs from wheel
- Verifies the installation

### 3. Dockerfile Validation Job
- Creates a test Dockerfile for Nuclei scanner
- Builds the Docker image with acido and Nuclei
- Tests both Nuclei and acido installations in the container

### 4. Lint Job
- Runs flake8 for code quality checks
- Validates all Python files

## Running Tests Locally

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Import Tests
```bash
python -c "from acido.utils.decoration import __version__; print('acido version:', __version__)"
python -m acido.cli --help
```

### Build and Test Distribution
```bash
python -m pip install build
python -m build
pip install dist/*.whl
```

### Test Nuclei Docker Build
```bash
# Create the Dockerfile (see CI workflow)
docker build -f Dockerfile.nuclei -t acido-nuclei:test .
docker run --rm acido-nuclei:test nuclei -version
```

## Workflow Triggers

The CI workflow runs on:
- Every pull request to `main` or `master` branches
- Every push to `main` or `master` branches

## Notes

- The workflow can run without Azure credentials, but some tests may be skipped
- Docker tests require Docker to be available in the CI environment
- The Nuclei Dockerfile test demonstrates the integration pattern described in the README
