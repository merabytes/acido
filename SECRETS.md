# Acido Secrets Sharing Service

A OneTimeSecret-like service built on AWS Lambda and Azure KeyVault that allows secure sharing of secrets with one-time access.

## Overview

The Acido Secrets Sharing Service provides a simple yet secure way to share sensitive information. Secrets are:
- Stored securely in Azure KeyVault
- Identified by a unique UUID
- Accessible only once (retrieved and immediately deleted)

This implementation follows the OneTimeSecret pattern where secrets self-destruct after being accessed.

## Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Client    │────────▶│  AWS Lambda      │────────▶│  Azure KeyVault │
│             │         │  (Secrets)       │         │                 │
└─────────────┘         └──────────────────┘         └─────────────────┘
                              │
                              │
                        ┌─────▼──────┐
                        │  Generate  │
                        │    UUID    │
                        └────────────┘
```

## Features

- **Create Secret**: Store a secret and receive a unique UUID
- **Retrieve Secret**: Get the secret once using the UUID (auto-deletes after retrieval)
- **Secure Storage**: All secrets stored in Azure KeyVault
- **Serverless**: Runs on AWS Lambda with automatic scaling
- **Continuous Deployment**: Automated deployment via GitHub Actions
- **Bot Protection**: Optional CloudFlare Turnstile integration for spam prevention

## API Reference

### Create Secret

Store a new secret and receive a UUID to access it.

**Request (without Turnstile):**
```json
{
  "action": "create",
  "secret": "Your secret message here"
}
```

**Request (with Turnstile enabled):**
```json
{
  "action": "create",
  "secret": "Your secret message here",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Response (201 Created):**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Secret created successfully"
}
```

**Response (400 Bad Request - Turnstile enabled, token missing):**
```json
{
  "error": "Missing required field: turnstile_token (bot protection enabled)"
}
```

**Response (403 Forbidden - Invalid Turnstile token):**
```json
{
  "error": "Invalid or expired Turnstile token"
}
```

### Retrieve Secret

Retrieve and delete a secret using its UUID (one-time access).

**Request (without Turnstile):**
```json
{
  "action": "retrieve",
  "uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Request (with Turnstile enabled):**
```json
{
  "action": "retrieve",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Response (200 OK):**
```json
{
  "secret": "Your secret message here",
  "message": "Secret retrieved and deleted successfully"
}
```

**Response (404 Not Found):**
```json
{
  "error": "Secret not found or already accessed"
}
```

## Deployment

### Prerequisites

1. **AWS Account** with:
   - ECR repository: `acido-secrets`
   - Lambda function: `AcidoSecrets`
   - Appropriate IAM permissions

2. **Azure Account** with:
   - Key Vault created and named
   - Service Principal with Key Vault access

3. **GitHub Secrets** configured:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `ECR_REGISTRY`
   - `KEY_VAULT_NAME`
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`

4. **CloudFlare Turnstile** (Optional - for bot protection):
   - Create a Turnstile site at https://dash.cloudflare.com/
   - Get the Site Key (for frontend) and Secret Key (for backend)
   - Add `CF_SECRET_KEY` to GitHub Secrets and Lambda environment variables

### Automated Deployment

The service automatically deploys to AWS Lambda when changes are pushed to the `main` branch.

See `.github/workflows/deploy-lambda-secrets.yml` for the deployment workflow.

### Manual Deployment

1. **Build the Docker image:**
```bash
docker build -t acido-secrets:latest -f Dockerfile.lambda.secrets .
```

2. **Tag and push to ECR:**
```bash
docker tag acido-secrets:latest <ECR_REGISTRY>/acido-secrets:latest
docker push <ECR_REGISTRY>/acido-secrets:latest
```

3. **Update Lambda function:**
```bash
aws lambda update-function-code \
  --function-name AcidoSecrets \
  --image-uri <ECR_REGISTRY>/acido-secrets:latest
```

4. **Set environment variables (without Turnstile):**
```bash
aws lambda update-function-configuration \
  --function-name AcidoSecrets \
  --environment "Variables={
    KEY_VAULT_NAME=<your-vault-name>,
    AZURE_TENANT_ID=<tenant-id>,
    AZURE_CLIENT_ID=<client-id>,
    AZURE_CLIENT_SECRET=<client-secret>
  }"
```

5. **Set environment variables (with Turnstile):**
```bash
aws lambda update-function-configuration \
  --function-name AcidoSecrets \
  --environment "Variables={
    KEY_VAULT_NAME=<your-vault-name>,
    AZURE_TENANT_ID=<tenant-id>,
    AZURE_CLIENT_ID=<client-id>,
    AZURE_CLIENT_SECRET=<client-secret>,
    CF_SECRET_KEY=<cloudflare-turnstile-secret-key>
  }"
```

## CloudFlare Turnstile Integration

CloudFlare Turnstile provides bot protection to prevent abuse of the secrets service. It's **optional** and only activated when the `CF_SECRET_KEY` environment variable is set.

### Setup

1. **Create a Turnstile Site:**
   - Go to https://dash.cloudflare.com/
   - Navigate to Turnstile
   - Create a new site
   - Choose "Managed" or "Non-Interactive" mode
   - Copy the Site Key and Secret Key

2. **Configure Lambda:**
   - Add `CF_SECRET_KEY` to your Lambda environment variables
   - Deploy the updated configuration

3. **Frontend Integration:**
   ```html
   <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
   
   <div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY"></div>
   ```

4. **Send Token with Request:**
   ```javascript
   const turnstileToken = document.querySelector('[name="cf-turnstile-response"]').value;
   
   fetch(lambdaUrl, {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       action: 'create',
       secret: 'my-secret',
       turnstile_token: turnstileToken
     })
   });
   ```

### How It Works

- **When CF_SECRET_KEY is NOT set**: Turnstile validation is skipped entirely
- **When CF_SECRET_KEY is set**: All requests must include a valid `turnstile_token`
- Invalid or missing tokens return 403 Forbidden
- The service validates tokens with CloudFlare's API
- Remote IP is extracted from Lambda context when available

## Testing

### Unit Tests

Run the test suite:
```bash
# Test VaultManager extensions
python -m unittest test_vault_manager -v

# Test Lambda handler
python -m unittest test_lambda_handler_secrets -v
```

### Manual Testing

1. **Create a secret:**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @example_lambda_secrets_create_payload.json
```

2. **Retrieve the secret (using UUID from step 1):**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @example_lambda_secrets_retrieve_payload.json
```

3. **Try retrieving again (should fail with 404):**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @example_lambda_secrets_retrieve_payload.json
```

## Example Payloads

Example request payloads are provided:
- `example_lambda_secrets_create_payload.json` - Create a secret
- `example_lambda_secrets_retrieve_payload.json` - Retrieve a secret

## Security Considerations

1. **One-Time Access**: Secrets are automatically deleted after retrieval
2. **Azure KeyVault**: Industry-standard secret storage
3. **HTTPS Only**: All communication should be over HTTPS
4. **No Logging**: Secrets should never be logged
5. **Time Limits**: Consider adding TTL for secrets in Key Vault

## VaultManager API Extensions

The `VaultManager` class has been extended with the following methods:

```python
# Create or update a secret
vault.set_secret(secret_name, secret_value)

# Delete a secret
vault.delete_secret(secret_name)

# Check if a secret exists
exists = vault.secret_exists(secret_name)
```

## Troubleshooting

### Common Issues

**Lambda timeout:**
- Default timeout is 3 seconds, increase if needed for Key Vault operations

**Key Vault access denied:**
- Verify Service Principal has `Get`, `Set`, `Delete` permissions
- Check that environment variables are correctly set

**Secret not found on first access:**
- Wait a few seconds after creation for Key Vault replication
- Verify the UUID is correct

## Related Files

- `lambda_handler_secrets.py` - Lambda handler implementation
- `acido/azure_utils/VaultManager.py` - Extended VaultManager class
- `Dockerfile.lambda.secrets` - Docker image for Lambda
- `.github/workflows/deploy-lambda-secrets.yml` - CD pipeline
- `test_vault_manager.py` - VaultManager tests
- `test_lambda_handler_secrets.py` - Lambda handler tests

## License

MIT License - See LICENSE file for details

## Contributors

- Xavier Álvarez (xalvarez@merabytes.com)
- Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)
