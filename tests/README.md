# Acido Tests

This directory contains all unit and integration tests for the Acido project.

## Test Files

### Core Functionality Tests

- **test_create_with_packages.py** - Tests for creating Azure container images with various security tools and packages
- **test_instance_manager_logs.py** - Tests for Azure Container Instance management, logging, and monitoring functionality
- **test_lambda_integration.py** - Integration tests for AWS Lambda deployment functionality

### Lambda Handler Tests

- **test_lambda_handler.py** - Unit tests for the AWS Lambda handler that orchestrates Acido container deployments
- **test_lambda_handler_secrets.py** - Tests for the AWS Lambda secrets sharing service handler

### Azure Services Tests

- **test_vault_manager.py** - Tests for Azure KeyVault integration and secret management

## Running Tests

### Run All Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Run Specific Test File

```bash
python -m unittest tests.test_lambda_handler -v
```

### Run Individual Test

```bash
python -m unittest tests.test_lambda_handler.TestLambdaHandler.test_basic_deployment -v
```

## Test Requirements

Most tests use mocking to avoid requiring actual Azure credentials. However, some integration tests may require:

- Azure credentials (for integration tests)
- AWS Lambda environment variables (for Lambda integration tests)
- Docker installed (for image creation tests)

## Environment Variables for Testing

When running tests that interact with Azure services, configure these environment variables:

- `AZURE_RESOURCE_GROUP` - Azure resource group name
- `IMAGE_REGISTRY_SERVER` - Azure Container Registry server URL
- `IMAGE_REGISTRY_USERNAME` - Registry username
- `IMAGE_REGISTRY_PASSWORD` - Registry password
- `STORAGE_ACCOUNT_NAME` - Azure Storage account name
- `STORAGE_ACCOUNT_KEY` - Storage account key (optional)

## CI/CD

Tests are automatically run on pull requests and pushes to the main branch via GitHub Actions. See `.github/workflows/ci.yml` for the complete CI configuration.
