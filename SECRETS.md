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
- **Check Secret**: Check if a secret is encrypted without retrieving it (non-destructive)
- **Password Encryption**: Optional client-side password protection for secrets
- **Time-based Expiration**: Optional expiration time for automatic secret deletion
- **Secure Storage**: All secrets stored in Azure KeyVault with explicit encryption metadata
- **Serverless**: Runs on AWS Lambda with automatic scaling
- **Continuous Deployment**: Automated deployment via GitHub Actions
- **Bot Protection**: Optional CloudFlare Turnstile integration for spam prevention

## How It Works

The API provides three main operations:

1. **Create**: Store a secret (with optional password encryption and/or expiration time) and get a UUID
2. **Check**: Verify if a secret is encrypted and/or has expiration before attempting to retrieve it
3. **Retrieve**: Get the secret once (with password if encrypted) and auto-delete

### Encryption Metadata

When creating a secret, the service stores up to three items in Azure KeyVault:
- `{uuid}` - The actual secret value (encrypted or plaintext)
- `{uuid}-metadata` - Explicit marker indicating "encrypted" or "plaintext"
- `{uuid}-expires` - (Optional) UNIX timestamp expiration

This ensures bulletproof detection of encryption status without content inspection, preventing false positives from base64-encoded data.

### Time-based Expiration

Secrets can be created with an optional expiration time:
- Provide `expires_at` as a UNIX timestamp (seconds since epoch, e.g., 1735689599)
- Expired secrets are automatically detected and deleted when accessed
- Returns HTTP 410 Gone for expired secrets
- Expiration is checked during both `check` and `retrieve` operations

## API Reference

### Create Secret

Store a new secret and receive a UUID to access it. Optionally encrypt with a password and/or set an expiration time.

**Request (plaintext secret):**
```json
{
  "action": "create",
  "secret": "Your secret message here",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Request (password-encrypted secret):**
```json
{
  "action": "create",
  "secret": "Your secret message here",
  "password": "your-encryption-password",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Request (secret with expiration time):**
```json
{
  "action": "create",
  "secret": "Your secret message here",
  "expires_at": 1735689599,
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Request (password-encrypted secret with expiration):**
```json
{
  "action": "create",
  "secret": "Your secret message here",
  "password": "your-encryption-password",
  "expires_at": 1735689599,
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

**Response (201 Created - with expiration):**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Secret created successfully",
  "expires_at": 1735689599
}
```

**Notes:**
- If `password` is provided, the secret is encrypted with AES-256 using PBKDF2 key derivation
- The same password must be provided during retrieval to decrypt
- Metadata is stored to track encryption status (bulletproof detection)
- If `expires_at` is provided, the secret will automatically expire and be deleted at that time
- `expires_at` must be a UNIX timestamp (seconds since epoch) and in the future
- Expired secrets return a 410 Gone status and are automatically deleted

**Response (400 Bad Request - Turnstile enabled, token missing):**
```json
{
  "error": "Missing required field: turnstile_token (bot protection enabled)"
}
```

**Response (400 Bad Request - Invalid expiration):**
```json
{
  "error": "expires_at must be in the future"
}
```

**Response (403 Forbidden - Invalid Turnstile token):**
```json
{
  "error": "Invalid or expired Turnstile token"
}
```

### Check Secret

Check if a secret is encrypted without retrieving or deleting it. This is useful for frontend applications to conditionally render password input fields.

**Request:**
```json
{
  "action": "check",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Response (200 OK - Encrypted secret):**
```json
{
  "encrypted": true,
  "requires_password": true
}
```

**Response (200 OK - Plaintext secret):**
```json
{
  "encrypted": false,
  "requires_password": false
}
```

**Response (200 OK - Secret with expiration):**
```json
{
  "encrypted": false,
  "requires_password": false,
  "expires_at": 1735689599
}
```

**Response (404 Not Found):**
```json
{
  "error": "Secret not found or already accessed"
}
```

**Response (410 Gone - Secret expired):**
```json
{
  "error": "Secret has expired and has been deleted",
  "expired_at": 1735689599
}
```

**Notes:**
- Non-destructive operation - secret remains accessible after check
- Uses stored metadata for bulletproof encryption detection
- No content inspection or heuristics - 100% reliable
- Frontend can use `requires_password` to show/hide password input
- If secret has expiration, `expires_at` field will be included in the response
- Expired secrets return 410 Gone and are automatically deleted

### Retrieve Secret

Retrieve and delete a secret using its UUID (one-time access). Provide password if the secret is encrypted.

**Request (plaintext secret):**
```json
{
  "action": "retrieve",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "turnstile_token": "cloudflare-turnstile-response-token"
}
```

**Request (encrypted secret with password):**
```json
{
  "action": "retrieve",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "password": "your-encryption-password",
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

**Response (400 Bad Request - Missing password for encrypted secret):**
```json
{
  "error": "Password required for encrypted secret"
}
```

**Response (400 Bad Request - Wrong password):**
```json
{
  "error": "Decryption failed: Invalid password or corrupted data"
}
```

**Response (404 Not Found):**
```json
{
  "error": "Secret not found or already accessed"
}
```

**Response (410 Gone - Secret expired):**
```json
{
  "error": "Secret has expired and has been deleted",
  "expired_at": 1735689599
}
```

**Notes:**
- Secret is automatically deleted after successful retrieval (one-time access)
- If secret is encrypted, password must match the one used during creation
- Wrong password or missing password for encrypted secrets returns 400 error and secret remains accessible for retry
- Multiple password attempts are allowed until correct password is provided
- Secret is only deleted upon successful decryption and retrieval
- Expired secrets return 410 Gone status and are automatically deleted from storage

## Workflow Examples

### Basic Workflow (Plaintext Secret)

1. **Create** a plaintext secret:
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "create",
       "secret": "Meet me at the coffee shop at 3pm",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"uuid": "abc-123", "message": "Secret created successfully"}`

2. **Share** the UUID with recipient: `https://yourapp.com/view/abc-123`

3. **Check** if password is needed (optional):
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "check",
       "uuid": "abc-123",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"encrypted": false, "requires_password": false}`

4. **Retrieve** the secret:
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "retrieve",
       "uuid": "abc-123",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"secret": "Meet me at the coffee shop at 3pm", ...}`

5. **Try again** - fails with 404 (already accessed)

### Advanced Workflow (Password-Encrypted Secret)

1. **Create** an encrypted secret:
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "create",
       "secret": "Database password: super_secret_123",
       "password": "myStrongPassword2024",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"uuid": "xyz-789", "message": "Secret created successfully"}`

2. **Share** UUID and password separately:
   - Email: "Here's the secret UUID: xyz-789"
   - SMS: "Password: myStrongPassword2024"

3. **Check** encryption status:
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "check",
       "uuid": "xyz-789",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"encrypted": true, "requires_password": true}`
   (Frontend shows password input field)

4. **Retrieve** with password:
   ```bash
   curl -X POST https://lambda-url/secrets \
     -H "Content-Type: application/json" \
     -d '{
       "action": "retrieve",
       "uuid": "xyz-789",
       "password": "myStrongPassword2024",
       "turnstile_token": "token..."
     }'
   ```
   Response: `{"secret": "Database password: super_secret_123", ...}`

5. **Wrong password** - returns 400 but secret remains accessible for retry

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
   - `CORS_ORIGIN` (Optional - defaults to `https://secrets.merabytes.com`)

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

4. **Set environment variables (minimal configuration):**
```bash
aws lambda update-function-configuration \
  --function-name AcidoSecrets \
  --environment "Variables={
    KEY_VAULT_NAME=<your-vault-name>,
    AZURE_TENANT_ID=<tenant-id>,
    AZURE_CLIENT_ID=<client-id>,
    AZURE_CLIENT_SECRET=<client-secret>,
    CORS_ORIGIN=https://secrets.merabytes.com
  }"
```

5. **Set environment variables (with all optional features):**
```bash
aws lambda update-function-configuration \
  --function-name AcidoSecrets \
  --environment "Variables={
    KEY_VAULT_NAME=<your-vault-name>,
    AZURE_TENANT_ID=<tenant-id>,
    AZURE_CLIENT_ID=<client-id>,
    AZURE_CLIENT_SECRET=<client-secret>,
    CORS_ORIGIN=<your-cors-origin-url>,
    CF_SECRET_KEY=<cloudflare-turnstile-secret-key>
  }"
```

## CORS Configuration

The Lambda function supports Cross-Origin Resource Sharing (CORS) to allow web applications to interact with the secrets API. The CORS origin URL can be configured through the `CORS_ORIGIN` environment variable.

### Configuration

- **Default**: If not specified, defaults to `https://secrets.merabytes.com`
- **Custom**: Set `CORS_ORIGIN` environment variable to your frontend URL

**Example:**
```bash
# Set custom CORS origin
aws lambda update-function-configuration \
  --function-name AcidoSecrets \
  --environment "Variables={...,CORS_ORIGIN=https://myapp.example.com}"
```

**In GitHub Actions:**
Add `CORS_ORIGIN` to your repository secrets to configure it during deployment.

### CORS Headers

The service responds with the following CORS headers:
- `Access-Control-Allow-Origin`: Configurable via `CORS_ORIGIN` (default: `https://secrets.merabytes.com`)
- `Access-Control-Allow-Methods`: `POST, OPTIONS`
- `Access-Control-Allow-Headers`: `Content-Type`

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
  -d @examples/example_lambda_secrets_create_payload.json
```

2. **Check if the secret is encrypted (using UUID from step 1):**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @examples/example_lambda_secrets_check_payload.json
```

3. **Retrieve the secret (using UUID from step 1):**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @examples/example_lambda_secrets_retrieve_payload.json
```

4. **Try retrieving again (should fail with 404):**
```bash
curl -X POST https://<lambda-url>/secrets \
  -H "Content-Type: application/json" \
  -d @examples/example_lambda_secrets_retrieve_payload.json
```

## Example Payloads

Example request payloads are provided in the `examples/` directory:
- `example_lambda_secrets_create_payload.json` - Create a secret (with optional password)
- `example_lambda_secrets_check_payload.json` - Check if a secret is encrypted
- `example_lambda_secrets_retrieve_payload.json` - Retrieve a secret (with optional password)

**Note:** Remember to include `turnstile_token` in all requests if CloudFlare Turnstile is enabled.

## Security Considerations

1. **One-Time Access**: Secrets are automatically deleted after retrieval
2. **Password Encryption**: Optional AES-256 encryption with PBKDF2 (100,000 iterations)
3. **Bulletproof Encryption Detection**: Metadata storage ensures reliable encryption status tracking
4. **Azure KeyVault**: Industry-standard secret storage with access controls
5. **HTTPS Only**: All communication should be over HTTPS
6. **No Logging**: Secrets should never be logged
7. **Bot Protection**: Optional CloudFlare Turnstile prevents automated abuse
8. **Secure Deletion**: Secrets deleted even if decryption fails (prevents brute force)
9. **Time Limits**: Consider adding TTL for secrets in Key Vault (future enhancement)

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
