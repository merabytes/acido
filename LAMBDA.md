# AWS Lambda Deployment for Acido

This directory contains the necessary files to deploy acido as an AWS Lambda function.

## Overview

The Lambda function allows you to invoke acido's distributed scanning capabilities through AWS Lambda, making it easy to integrate security scanning into your serverless workflows.

## Files

- `lambda_handler.py` - Lambda function handler
- `Dockerfile.lambda` - Docker image for Lambda deployment
- `.github/workflows/deploy-lambda.yml` - CI/CD workflow for automatic deployment

## Deployment

### Prerequisites

1. AWS Account with permissions to:
   - Create/update Lambda functions
   - Push to ECR (Elastic Container Registry)
   - Update Lambda environment variables

2. GitHub repository secrets configured:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `ECR_REGISTRY` (e.g., `318257425368.dkr.ecr.eu-west-1.amazonaws.com`)
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
   - `AZURE_RESOURCE_GROUP`
   - `IMAGE_REGISTRY_SERVER`
   - `IMAGE_REGISTRY_USERNAME`
   - `IMAGE_REGISTRY_PASSWORD`
   - `STORAGE_ACCOUNT_NAME`
   - `LAMBDA_FUNCTION_URL` (optional, for testing after deployment)

### Automatic Deployment

The Lambda function is automatically deployed on pushes to the `main` branch via GitHub Actions.

The workflow:
1. Builds the Docker image using `Dockerfile.lambda`
2. Tags and pushes to Amazon ECR
3. Updates the Lambda function with the new image
4. Updates environment variables from secrets
5. Tests the Lambda Function URL (if `LAMBDA_FUNCTION_URL` secret is set)

### Manual Deployment

```bash
# Set your ECR registry
ECR_REGISTRY="your-account-id.dkr.ecr.your-region.amazonaws.com"

# Login to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push
docker build -t $ECR_REGISTRY/acido:latest -f Dockerfile.lambda .
docker push $ECR_REGISTRY/acido:latest

# Update Lambda
aws lambda update-function-code \
  --function-name Acido \
  --image-uri $ECR_REGISTRY/acido:latest
```

## Usage

### Event Format

The Lambda function accepts JSON events with the following structure:

```json
{
  "image": "nmap",
  "targets": ["merabytes.com", "uber.com", "facebook.com"],
  "task": "nmap -iL input -p 0-1000"
}
```

Or with a body wrapper (e.g., from API Gateway):

```json
{
  "body": {
    "image": "nmap",
    "targets": ["merabytes.com", "uber.com", "facebook.com"],
    "task": "nmap -iL input -p 0-1000"
  }
}
```

### Parameters

- **image** (required): Name of the Docker image to use (e.g., "nmap", "nuclei")
- **targets** (required): Array of target URLs/IPs to scan
- **task** (required): Command to execute (use "input" as the filename placeholder)
- **fleet_name** (optional): Name for the container fleet (default: "lambda-fleet")
- **num_instances** (optional): Number of container instances (default: number of targets)
- **rm_when_done** (optional): Clean up containers after completion (default: true)

### Response Format

Success response (200):
```json
{
  "statusCode": 200,
  "body": {
    "fleet_name": "lambda-fleet",
    "instances": 3,
    "image": "nmap",
    "outputs": {
      "container-1": "scan output...",
      "container-2": "scan output...",
      "container-3": "scan output..."
    }
  }
}
```

Error response (400/500):
```json
{
  "statusCode": 400,
  "body": {
    "error": "Missing required fields: targets"
  }
}
```

### Testing the Lambda Function

#### Using AWS CLI

You can test the Lambda function using the AWS CLI:

```bash
aws lambda invoke \
  --function-name Acido \
  --payload '{"image": "nmap", "targets": ["merabytes.com", "uber.com", "facebook.com"], "task": "nmap -iL input -p 0-1000"}' \
  response.json

cat response.json
```

#### Using Lambda Function URL

If you've configured a Lambda Function URL:

```bash
curl -X POST "https://your-function-url.lambda-url.eu-west-1.on.aws/" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Merabytes-Portal" \
  -d @example_lambda_payload.json
```

The deployment workflow automatically tests the Function URL after each deployment if the `LAMBDA_FUNCTION_URL` secret is configured.

#### Using AWS Console

1. Go to Lambda → Functions → Acido
2. Click "Test"
3. Create a new test event with the example payload
4. Click "Test" to invoke

## Environment Variables

The Lambda function requires the following environment variables (automatically set by the deployment workflow):

- `AZURE_TENANT_ID` - Azure tenant ID for authentication
- `AZURE_CLIENT_ID` - Azure client/application ID
- `AZURE_CLIENT_SECRET` - Azure client secret
- `AZURE_RESOURCE_GROUP` - Azure resource group for container instances
- `IMAGE_REGISTRY_SERVER` - Azure Container Registry server
- `IMAGE_REGISTRY_USERNAME` - Registry username
- `IMAGE_REGISTRY_PASSWORD` - Registry password
- `STORAGE_ACCOUNT_NAME` - Azure storage account for blob storage

## Architecture

```
AWS Lambda → Acido Handler → Azure Container Instances (Fleet)
                ↓
            Azure Blob Storage (Input/Output)
                ↓
            Scan Results (Returned to Lambda)
```

The Lambda function:
1. Parses the incoming event
2. Creates a temporary input file with targets
3. Initializes acido with Azure credentials
4. Spawns a fleet of Azure Container Instances
5. Distributes targets across containers
6. Collects and returns outputs
7. Optionally cleans up containers

## Limitations

- Lambda execution time limit: 15 minutes (set appropriate timeout)
- Lambda memory: Configure based on workload (recommend 1GB+)
- Cold starts: First invocation may be slower
- Azure rate limits apply to container creation

## Troubleshooting

### Check Lambda logs
```bash
aws logs tail /aws/lambda/Acido --follow
```

### Test locally with SAM
```bash
sam local invoke Acido --event test-event.json
```

### Common issues

1. **Timeout errors**: Increase Lambda timeout setting
2. **Memory errors**: Increase Lambda memory allocation
3. **Azure authentication errors**: Verify environment variables are set correctly
4. **Container creation errors**: Check Azure quotas and permissions

## Security Considerations

- Store Azure credentials as encrypted environment variables
- Use IAM roles with least privilege for Lambda
- Consider using AWS Secrets Manager for sensitive data
- Review and restrict Lambda VPC configuration if needed
- Enable CloudWatch logging for audit trail
