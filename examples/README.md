# Acido Examples

This directory contains example payload files for various Acido AWS Lambda deployments.

## Lambda Deployment Example

### example_lambda_payload.json

Example payload for deploying security scanning containers via AWS Lambda.

**Purpose:** Demonstrates how to trigger a distributed security scan using Acido's Lambda function.

**Usage:**
```bash
curl -X POST "https://your-function-url.lambda-url.region.on.aws/" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Merabytes-Portal" \
  -d @examples/example_lambda_payload.json
```

**Payload Structure:**
```json
{
  "image": "kali-rolling",
  "targets": [
    "merabytes.com",
    "uber.com",
    "facebook.com"
  ],
  "task": "nmap -iL input -p 0-1000"
}
```

**Fields:**
- `image` - Docker image name (must be created with `acido create` first)
- `targets` - List of target hosts/URLs to scan
- `task` - Command to execute on each container

**Documentation:** See [LAMBDA.md](../LAMBDA.md) for complete Lambda deployment guide.

---

## Secrets Sharing Service Examples

The secrets sharing service provides a OneTimeSecret-like functionality for secure one-time secret sharing.

### example_lambda_secrets_create_payload.json

Example payload for creating a secret that can be retrieved only once.

**Purpose:** Create a secure, one-time accessible secret stored in Azure KeyVault.

**Usage:**
```bash
curl -X POST https://your-lambda-url/secrets \
  -H "Content-Type: application/json" \
  -d @examples/example_lambda_secrets_create_payload.json
```

**Payload Structure:**
```json
{
  "action": "create",
  "secret": "This is my super secret message that I want to share only once!",
  "password": "optional-password-for-encryption"
}
```

**Fields:**
- `action` - Must be "create"
- `secret` - The secret message to store
- `password` - (Optional) Password for additional encryption

**Response:** Returns a UUID that can be used to retrieve the secret once.

---

### example_lambda_secrets_retrieve_payload.json

Example payload for retrieving a previously created secret.

**Purpose:** Retrieve a secret using the UUID from the create response. The secret is automatically deleted after retrieval.

**Usage:**
```bash
curl -X POST https://your-lambda-url/secrets \
  -H "Content-Type: application/json" \
  -d @examples/example_lambda_secrets_retrieve_payload.json
```

**Payload Structure:**
```json
{
  "action": "retrieve",
  "uuid": "replace-with-actual-uuid-from-create-response",
  "password": "same-password-used-during-creation-if-encrypted"
}
```

**Fields:**
- `action` - Must be "retrieve"
- `uuid` - The UUID returned from the create request
- `password` - (Optional) Password if the secret was encrypted

**Important:** Each secret can only be retrieved once. After retrieval, it is automatically deleted from Azure KeyVault.

**Documentation:** See [SECRETS.md](../SECRETS.md) for complete secrets service documentation.

---

## Testing Examples Locally

You can test these payloads locally using the Lambda handlers:

```bash
# Test Lambda deployment handler
python lambda_handler.py < examples/example_lambda_payload.json

# Test secrets create
python lambda_handler_secrets.py < examples/example_lambda_secrets_create_payload.json

# Test secrets retrieve (after getting UUID from create)
python lambda_handler_secrets.py < examples/example_lambda_secrets_retrieve_payload.json
```

## Deployment

These examples are used by GitHub Actions workflows for automated deployment testing:
- `.github/workflows/deploy-lambda.yml` - Tests Lambda deployment
- `.github/workflows/deploy-lambda-secrets.yml` - Tests secrets service

## Security Notes

1. **One-Time Access**: Secrets are deleted immediately after retrieval
2. **HTTPS Required**: Always use HTTPS in production
3. **Optional Encryption**: Use password field for additional encryption layer
4. **KeyVault Storage**: All secrets are stored securely in Azure KeyVault
5. **UUID-Based**: Secrets are accessed via UUID, not predictable URLs
