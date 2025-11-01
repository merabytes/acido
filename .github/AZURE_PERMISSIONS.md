# Azure Permissions and Service Principal Setup for acido

This document provides detailed instructions for setting up the required Azure permissions and creating a Service Principal with the appropriate roles for acido to function properly.

## Overview

Acido requires access to several Azure services to deploy and manage distributed container instances. The tool uses Azure authentication (either Azure CLI, Managed Identity, or Service Principal) to interact with:

- **Azure Container Instances (ACI)** - Deploy and manage containers
- **Azure Storage (Blob)** - Store and retrieve input/output files
- **Azure Container Registry (ACR)** - Pull Docker images
- **Azure Virtual Network** - Configure network profiles and public IPs
- **Azure Key Vault** (optional) - Store and retrieve secrets

## Required Azure Permissions

Based on the operations performed by acido, the following Azure RBAC roles are required:

### Core Permissions (Required)

| Service | Role | Purpose |
|---------|------|---------|
| Container Instances | `Contributor` or `Container Instances Contributor` | Create, delete, and manage container groups and instances |
| Storage Accounts | `Storage Blob Data Contributor` | Upload/download files to/from blob storage |
| Storage Accounts | `Storage Account Contributor` | List storage account keys |
| Container Registry | `AcrPull` | Pull Docker images from ACR |
| Virtual Network | `Network Contributor` | Create and manage virtual networks, subnets, and IP addresses |
| Resource Group | `Reader` | List and read resource group information |

### Optional Permissions

| Service | Role | Purpose |
|---------|------|---------|
| Key Vault | `Key Vault Secrets User` | Read secrets from Azure Key Vault |

## Creating a Service Principal

### Option 1: Using Azure CLI (Recommended)

#### Step 1: Create a Service Principal

```bash
# Set your variables
SUBSCRIPTION_ID="<your-subscription-id>"
RESOURCE_GROUP="<your-resource-group>"
SP_NAME="acido-service-principal"

# Create the service principal
az ad sp create-for-rbac \
  --name $SP_NAME \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

This command will output JSON containing your credentials:

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

**Important:** Save these credentials securely. The `clientSecret` cannot be retrieved later.

#### Step 2: Assign Specific Roles (Fine-grained Permissions)

For better security, assign specific roles instead of the broad `Contributor` role:

```bash
# Get the Service Principal Object ID
SP_OBJECT_ID=$(az ad sp list --display-name $SP_NAME --query "[0].id" -o tsv)

# Assign Container Instances Contributor role
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Container Instances Contributor" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP

# Assign Storage Blob Data Contributor role
# (Replace STORAGE_ACCOUNT_NAME with your actual storage account name)
STORAGE_ACCOUNT_NAME="<your-storage-account>"
STORAGE_ACCOUNT_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Storage Blob Data Contributor" \
  --scope $STORAGE_ACCOUNT_ID

# Assign Storage Account Contributor role (to list keys)
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Storage Account Contributor" \
  --scope $STORAGE_ACCOUNT_ID

# Assign Network Contributor role
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Network Contributor" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP

# Assign AcrPull role for Container Registry
# (Replace ACR_NAME with your actual ACR name)
ACR_NAME="<your-acr-name>"
ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)

az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "AcrPull" \
  --scope $ACR_ID
```

#### Step 3 (Optional): Assign Key Vault Permissions

If you're using Azure Key Vault:

```bash
KEY_VAULT_NAME="<your-key-vault-name>"

az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KEY_VAULT_NAME
```

### Option 2: Using Azure Portal

1. **Navigate to Azure Active Directory**
   - Go to [Azure Portal](https://portal.azure.com)
   - Select "Azure Active Directory" from the left menu

2. **Register an Application**
   - Click "App registrations" → "New registration"
   - Name: `acido-service-principal`
   - Click "Register"

3. **Create a Client Secret**
   - In your app registration, go to "Certificates & secrets"
   - Click "New client secret"
   - Add a description and expiration period
   - Click "Add" and **copy the secret value immediately**

4. **Note Your Credentials**
   - Application (client) ID
   - Directory (tenant) ID
   - Client secret value

5. **Assign Roles**
   - Go to your Resource Group
   - Click "Access control (IAM)" → "Add role assignment"
   - Select the roles listed in the "Core Permissions" section above
   - For "Assign access to", select "User, group, or service principal"
   - Search for your app name (`acido-service-principal`)
   - Click "Save"
   - Repeat for each required role

## Configuring acido with Service Principal

Once you have created the Service Principal, configure acido to use it:

### Option 1: Environment Variables

Set the following environment variables:

```bash
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_CLIENT_ID="<client-id>"
export AZURE_CLIENT_SECRET="<client-secret>"
export AZURE_SUBSCRIPTION_ID="<subscription-id>"
```

Add these to your `~/.bashrc` or `~/.zshrc` for persistence:

```bash
# Add to ~/.bashrc or ~/.zshrc
export AZURE_TENANT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export AZURE_CLIENT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export AZURE_CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export AZURE_SUBSCRIPTION_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### Option 2: GitHub Actions Secrets

For CI/CD pipelines, add these as GitHub repository secrets:

1. Go to your repository on GitHub
2. Settings → Secrets and variables → Actions
3. Add the following secrets:
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_REGISTRY_SERVER`
   - `AZURE_REGISTRY_USERNAME`
   - `AZURE_REGISTRY_PASSWORD`

### Option 3: Interactive Prompt

If environment variables are not set, acido will prompt you for credentials when needed:

```bash
acido -f myfleet -n 5
Enter TENANT_ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Enter CLIENT_ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Enter CLIENT_SECRET: ********
```

## Authentication Methods Priority

Acido attempts authentication in the following order:

### For Cloud Deployments (Azure Container Instances)
1. **Managed Identity** (if `IDENTITY_CLIENT_ID` is set)
2. **Environment Credentials** (if `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` are set)

### For Local Development
1. **Azure CLI Credentials** (if logged in via `az login`)
2. **Environment Credentials** (if environment variables are set)
3. **Interactive Client Secret** (manual prompt)

## Verifying Permissions

To verify your Service Principal has the correct permissions:

```bash
# Login with Service Principal
az login --service-principal \
  --username $AZURE_CLIENT_ID \
  --password $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID

# Test Container Instances access
az container list --resource-group $RESOURCE_GROUP

# Test Storage access
az storage account list --resource-group $RESOURCE_GROUP

# Test ACR access
az acr repository list --name $ACR_NAME

# Test Network access
az network vnet list --resource-group $RESOURCE_GROUP
```

## Managed Identity for Container Instances

When acido creates container instances, it automatically assigns a User-Assigned Managed Identity to them. This allows containers to access Azure resources without storing credentials.

### Creating a User-Assigned Managed Identity

```bash
IDENTITY_NAME="acido-containers-identity"

# Create the managed identity
az identity create \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP

# Get the identity details
IDENTITY_ID=$(az identity show \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

IDENTITY_CLIENT_ID=$(az identity show \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP \
  --query clientId -o tsv)

# Assign Storage Blob Data Contributor role to the identity
az role assignment create \
  --assignee $IDENTITY_CLIENT_ID \
  --role "Storage Blob Data Contributor" \
  --scope $STORAGE_ACCOUNT_ID

# Assign Key Vault Secrets User role (if using Key Vault)
az role assignment create \
  --assignee $IDENTITY_CLIENT_ID \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KEY_VAULT_NAME
```

### Configure acido to use the Managed Identity

Set the managed identity in your container instances:

```bash
export IDENTITY_CLIENT_ID="$IDENTITY_CLIENT_ID"
```

## Security Best Practices

1. **Use Managed Identities** when possible (for containers running in Azure)
2. **Limit Scope** - Assign permissions only to specific resource groups, not subscriptions
3. **Use Specific Roles** - Avoid using `Owner` or overly broad `Contributor` roles
4. **Rotate Secrets** - Regularly rotate client secrets and access keys
5. **Monitor Access** - Use Azure Monitor to track resource access
6. **Use Key Vault** - Store sensitive configuration in Azure Key Vault instead of environment variables
7. **Set Expiration** - Configure client secret expiration dates
8. **Enable MFA** - Use multi-factor authentication for Azure portal access

## Troubleshooting

### "No permissions granted for the given credentials"

This error indicates the Service Principal lacks required permissions. Verify:
- Role assignments are correctly configured
- Service Principal is assigned to the correct resource group/resources
- Wait 5-10 minutes for role assignments to propagate

### "Authentication failed"

Check:
- Environment variables are correctly set
- Client secret is valid (not expired)
- `az login` is successful (for local development)
- Service Principal exists and is not disabled

### "Cannot access storage account"

Ensure:
- Service Principal has both `Storage Blob Data Contributor` AND `Storage Account Contributor` roles
- Storage account firewall allows access
- Managed Identity (if used) has blob storage permissions

## Additional Resources

- [Azure RBAC Documentation](https://docs.microsoft.com/azure/role-based-access-control/overview)
- [Azure Service Principal Documentation](https://docs.microsoft.com/azure/active-directory/develop/app-objects-and-service-principals)
- [Azure Managed Identities](https://docs.microsoft.com/azure/active-directory/managed-identities-azure-resources/overview)
- [Azure Container Instances Documentation](https://docs.microsoft.com/azure/container-instances/)

## Summary Checklist

- [ ] Create Service Principal with `az ad sp create-for-rbac`
- [ ] Assign Container Instances Contributor role
- [ ] Assign Storage Blob Data Contributor role
- [ ] Assign Storage Account Contributor role
- [ ] Assign Network Contributor role
- [ ] Assign AcrPull role for Container Registry
- [ ] (Optional) Assign Key Vault Secrets User role
- [ ] Set environment variables (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`)
- [ ] Create User-Assigned Managed Identity for containers
- [ ] Assign blob storage permissions to Managed Identity
- [ ] Test authentication with `az login --service-principal`
- [ ] Verify acido functionality with a test deployment
