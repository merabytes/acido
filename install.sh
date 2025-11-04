#!/usr/bin/env bash
###############################################################################
# install.sh
#
# Idempotent Azure bootstrap script for the `acido` project.
# Executes in Azure Cloud Shell (or any environment with Azure CLI >= 2.55).
#
# Creates / reconciles:
#   - (Optional) Resource Group
#   - Service Principal (Contributor OR Least Privilege mode)
#   - Azure Container Registry (ACR)
#   - Storage Account (+ default blob container 'acido', or override)
#   - User Assigned Managed Identity (optional)
#   - Key Vault (optional via -k/--kv) with RBAC and optional secrets
#
# Key Changes (this revision):
#   - Validates ACR name: lowercase alphanumeric, length 5–50
#   - Validates Storage Account name: lowercase alphanumeric, length 3–24
#   - Default blob container name is now ALWAYS 'acido' unless overridden
#   - **NEW** Optional Key Vault creation (-k/--kv) and secret seeding (--kv-secret)
#
# Safe to re-run: existing resources are reused; roles re-applied if absent;
# optional SP client secret rotated.
#
# Fast start (Contributor):
#   ./install.sh -s SUB_ID -g acido-rg -l eastus -p acido -a acidocr -S acidostore123
#
# Least privilege example:
#   ./install.sh -s SUB_ID -g acido-rg -l eastus -p acido -a acidocr \
#     -S acidostore123 --least-privilege --identity-name acido-id
#
# With Key Vault + a secret:
#   ./install.sh -s SUB -g acido-rg -l eastus -p acido -S acidostore123 \
#     -k acidokv --kv-secret STORAGE_CONN="DefaultEndpointsProtocol=https;..."
###############################################################################
set -Eeuo pipefail

###############################################################################
# Configuration Defaults
###############################################################################
SUBSCRIPTION_ID=""
RESOURCE_GROUP=""
LOCATION=""
SP_NAME=""
ACR_NAME=""
STORAGE_ACCOUNT_NAME=""
STORAGE_CONTAINER_NAME="acido"   # default container name
IDENTITY_NAME=""
LEAST_PRIVILEGE=false
CREATE_RG=false
GENERATE_CLIENT_SECRET=true
SHOW_SECRET=false
EMIT_ENV_FILE=""
RANDOM_SUFFIX_LEN=4
TAG_PROJECT="acido"
RETRY=18
RETRY_SLEEP=2
COLOR=true

# Key Vault options
KV_NAME=""
declare -a KV_SECRETS=()  # each item: name=value

###############################################################################
# Color Handling
###############################################################################
if [[ ! -t 1 ]]; then COLOR=false; fi
if $COLOR; then
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'
  C_BLUE=$'\033[34m';  C_DIM=$'\033[2m';    C_RESET=$'\033[0m'
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""; C_DIM=""; C_RESET=""
fi

###############################################################################
# Logging Helpers
###############################################################################
info()   { printf "%s[INFO]%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn()   { printf "%s[WARN]%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
note()   { printf "%s[NOTE]%s %s\n" "$C_BLUE" "$C_RESET" "$*"; }
dim()    { printf "%s[....]%s %s\n" "$C_DIM" "$C_RESET" "$*"; }
err()    { printf "%s[ERR ]%s %s\n"  "$C_RED" "$C_RESET" "$*" >&2; }
die()    { err "$*"; exit 1; }

###############################################################################
# usage: Display help information.
###############################################################################
usage() {
  cat <<EOF
install.sh - Provision Azure resources for 'acido'

Required:
  -s, --subscription-id ID          Azure Subscription ID
  -g, --resource-group NAME         Resource Group name
  -l, --location LOCATION           Azure region (for new resources)

Common:
  -p, --sp-name NAME                Service Principal name (default: acido)
  -a, --acr-name NAME               ACR name (lowercase alphanumeric, 5–50 chars)
  -S, --storage-account-name NAME   Storage Account name (lowercase alphanumeric, 3–24 chars)
      --create-storage-container C  Override blob container name (default: acido)
  -i, --identity-name NAME          Create User Assigned Managed Identity
      --least-privilege             Granular roles instead of Contributor
      --no-client-secret            Skip SP client secret generation
      --show-secret                 Print generated secret (not recommended)
      --emit-env-file FILE          Write environment exports to FILE
      --create-rg                   Create resource group if missing
      --randomize-acr               Append random suffix to ACR name
      --randomize-storage           Append random suffix to Storage name
      --random-suffix-len N         Length of random suffix (default: 4)
      --skip-color                  Disable colored output

Key Vault (optional):
  -k, --kv NAME                     Create/ensure Key Vault NAME with RBAC
      --kv-secret NAME=VALUE        Seed a secret (repeatable). Example: --kv-secret API_KEY=123

  -h, --help                        Show help

Examples:
  Fast start:
    ./install.sh -s SUB -g acido-rg -l eastus -p acido -a acidocr -S acidostore123

  Least privilege + identity + key vault:
    ./install.sh -s SUB -g acido-rg -l eastus -p acido -a acidocr -S acidostore123 \
      --least-privilege --identity-name acido-id -k acidokv \
      --kv-secret STORAGE_CONN="DefaultEndpointsProtocol=https;..." --emit-env-file acido.env
EOF
}

###############################################################################
# rand_suffix: Generate a random lowercase alphanumeric suffix.
# Arguments:
#   $1 (optional) length (default RANDOM_SUFFIX_LEN)
###############################################################################
rand_suffix() {
  local len="${1:-$RANDOM_SUFFIX_LEN}"
  tr -dc 'a-z0-9' </dev/urandom | head -c "$len"
}

###############################################################################
# validate_acr_name: Enforce ACR naming constraints.
# Rules: lowercase alphanumeric only, length 5–50.
###############################################################################
validate_acr_name() {
  local name="$1"
  [[ -z "$name" ]] && return 0
  if [[ ! "$name" =~ ^[a-z0-9]+$ ]]; then
    die "ACR name '$name' invalid: must be lowercase alphanumeric only."
  fi
  local len="${#name}"
  if (( len < 5 || len > 50 )); then
    die "ACR name '$name' invalid length $len: must be 5–50 characters."
  fi
}

###############################################################################
# validate_storage_name: Enforce Storage Account naming constraints.
# Rules: lowercase alphanumeric only, length 3–24.
###############################################################################
validate_storage_name() {
  local name="$1"
  [[ -z "$name" ]] && return 0
  if [[ ! "$name" =~ ^[a-z0-9]+$ ]]; then
    die "Storage account name '$name' invalid: must be lowercase alphanumeric only."
  fi
  local len="${#name}"
  if (( len < 3 || len > 24 )); then
    die "Storage account name '$name' invalid length $len: must be 3–24 characters."
  fi
}

###############################################################################
# parse_args: Parse CLI arguments into global variables.
###############################################################################
parse_args() {
  while (($#)); do
    case "$1" in
      -s|--subscription-id) SUBSCRIPTION_ID="$2"; shift 2 ;;
      -g|--resource-group)  RESOURCE_GROUP="$2"; shift 2 ;;
      -l|--location)        LOCATION="$2"; shift 2 ;;
      -p|--sp-name|--service-principal-name) SP_NAME="$2"; shift 2 ;;
      -a|--acr-name)        ACR_NAME="$2"; shift 2 ;;
      -S|--storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift 2 ;;
      --create-storage-container) STORAGE_CONTAINER_NAME="$2"; shift 2 ;;
      -i|--identity-name)   IDENTITY_NAME="$2"; shift 2 ;;
      --least-privilege)    LEAST_PRIVILEGE=true; shift ;;
      --no-client-secret)   GENERATE_CLIENT_SECRET=false; shift ;;
      --show-secret)        SHOW_SECRET=true; shift ;;
      --emit-env-file)      EMIT_ENV_FILE="$2"; shift 2 ;;
      --create-rg)          CREATE_RG=true; shift ;;
      --randomize-acr)      ACR_NAME="${ACR_NAME}-$(rand_suffix)"; shift ;;
      --randomize-storage)  STORAGE_ACCOUNT_NAME="${STORAGE_ACCOUNT_NAME}$(rand_suffix)"; shift ;;
      --random-suffix-len)  RANDOM_SUFFIX_LEN="$2"; shift 2 ;;
      --skip-color)         COLOR=false; shift ;;
      -k|--kv)              KV_NAME="$2"; shift 2 ;;
      --kv-secret)          KV_SECRETS+=("$2"); shift 2 ;;
      -h|--help)            usage; exit 0 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done
}

###############################################################################
# validate_inputs: Check required values; perform name validations.
###############################################################################
validate_inputs() {
  [[ -z "$SUBSCRIPTION_ID" ]] && die "Missing --subscription-id"
  [[ -z "$RESOURCE_GROUP" ]]  && die "Missing --resource-group"
  if [[ -z "$LOCATION" ]]; then
    warn "No --location; required if creating RG or new resources."
  fi

  validate_acr_name "$ACR_NAME"
  validate_storage_name "$STORAGE_ACCOUNT_NAME"

  if [[ -z "$ACR_NAME" ]]; then
    warn "No --acr-name; ACR creation skipped."
  fi
  if [[ -z "$STORAGE_ACCOUNT_NAME" ]]; then
    warn "No --storage-account-name; storage setup skipped."
  fi
  if ! $GENERATE_CLIENT_SECRET && [[ -z "$IDENTITY_NAME" ]]; then
    warn "Neither client secret generation nor identity provided; ensure SP already has credentials."
  fi
}

###############################################################################
# ensure_subscription: Verify Azure login & set subscription.
###############################################################################
ensure_subscription() {
  az account show >/dev/null 2>&1 || die "Not logged in. Run: az login"
  az account set --subscription "$SUBSCRIPTION_ID"
  info "Using subscription: $SUBSCRIPTION_ID"
}

###############################################################################
# ensure_rg: Create resource group if missing and flag set.
###############################################################################
ensure_rg() {
  local exists
  exists="$(az group exists --name "$RESOURCE_GROUP")"
  if [[ "$exists" == "false" ]]; then
    $CREATE_RG || die "RG '$RESOURCE_GROUP' missing. Use --create-rg to create."
    [[ -z "$LOCATION" ]] && die "Need --location to create resource group."
    info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'"
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags project="$TAG_PROJECT" 1>/dev/null
  else
    info "Resource group '$RESOURCE_GROUP' exists."
  fi
}

###############################################################################
# ensure_sp: Create or reuse service principal and optionally rotate secret.
###############################################################################
ensure_sp() {
  info "Ensuring Service Principal '$SP_NAME'..."
  APP_ID="$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv || true)"
  if [[ -z "$APP_ID" || "$APP_ID" == "null" ]]; then
    if $LEAST_PRIVILEGE; then
      info "Creating SP (skip assignment; least privilege)."
      az ad sp create-for-rbac --name "$SP_NAME" --skip-assignment 1>/dev/null
    else
      info "Creating SP with Contributor at RG scope."
      az ad sp create-for-rbac \
        --name "$SP_NAME" \
        --role Contributor \
        --scopes "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" 1>/dev/null
    fi
    APP_ID="$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv)"
  else
    info "SP exists (appId=$APP_ID)."
  fi

  dim "Resolving SP objectId..."
  for _ in $(seq 1 "$RETRY"); do
    SP_OBJECT_ID="$(az ad sp show --id "$APP_ID" --query id -o tsv 2>/dev/null || true)"
    [[ -n "$SP_OBJECT_ID" && "$SP_OBJECT_ID" != "null" ]] && break
    sleep "$RETRY_SLEEP"
  done
  [[ -z "$SP_OBJECT_ID" || "$SP_OBJECT_ID" == "null" ]] && die "Failed to resolve SP object id."
  info "SP objectId: $SP_OBJECT_ID"

  if $GENERATE_CLIENT_SECRET; then
    info "Rotating / generating client secret..."
    local display="acido-$(date +%Y%m%d%H%M%S)"
    GENERATED_SECRET_JSON="$(az ad app credential reset --id "$APP_ID" --display-name "$display" --years 1 --query '{secret:password}' -o json)"
    GENERATED_CLIENT_SECRET="$(echo "$GENERATED_SECRET_JSON" | jq -r '.secret')"
    if $SHOW_SECRET; then
      warn "Client Secret (store securely): $GENERATED_CLIENT_SECRET"
    else
      info "Client secret generated (hidden). Use --show-secret to display."
    fi
  fi
}

###############################################################################
# assign_roles: Apply granular roles or rely on Contributor.
###############################################################################
assign_roles() {
  if $LEAST_PRIVILEGE; then
    info "Assigning granular roles (ACI + Network)."
    az role assignment create --assignee "$SP_OBJECT_ID" \
      --role "Container Instances Contributor" \
      --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" 1>/dev/null || true
    az role assignment create --assignee "$SP_OBJECT_ID" \
      --role "Network Contributor" \
      --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" 1>/dev/null || true
  else
    info "Contributor mode: skipping granular ACI/network roles."
  fi
}

###############################################################################
# ensure_acr: Create or reuse ACR and assign AcrPull.
###############################################################################
ensure_acr() {
  [[ -z "$ACR_NAME" ]] && return
  if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    [[ -z "$LOCATION" ]] && die "Need --location to create ACR."
    info "Creating ACR '$ACR_NAME'..."
    az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" --sku Standard --admin-enabled true \
      --tags project="$TAG_PROJECT" 1>/dev/null
  else
    info "ACR '$ACR_NAME' exists."
    # Enable admin if not already enabled
    az acr update --name "$ACR_NAME" --admin-enabled true 1>/dev/null 2>&1 || true
  fi
  ACR_ID="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)"
  info "Assigning AcrPull and AcrPush roles."
  az role assignment create --assignee "$SP_OBJECT_ID" --role "AcrPull" --scope "$ACR_ID" 1>/dev/null || true
  az role assignment create --assignee "$SP_OBJECT_ID" --role "AcrPush" --scope "$ACR_ID" 1>/dev/null || true
}

###############################################################################
# ensure_storage: Create or reuse storage account & container; assign roles.
###############################################################################
ensure_storage() {
  [[ -z "$STORAGE_ACCOUNT_NAME" ]] && return
  if ! az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    [[ -z "$LOCATION" ]] && die "Need --location to create storage account."
    info "Creating Storage Account '$STORAGE_ACCOUNT_NAME'..."
    az storage account create \
      --name "$STORAGE_ACCOUNT_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --sku Standard_LRS \
      --kind StorageV2 \
      --tags project="$TAG_PROJECT" 1>/dev/null
  else
    info "Storage Account '$STORAGE_ACCOUNT_NAME' exists."
  fi
  STORAGE_ACCOUNT_ID="$(az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)"

  info "Assigning storage roles (Blob Data Contributor + Key Operator + Reader)."
  az role assignment create --assignee "$SP_OBJECT_ID" --role "Storage Blob Data Contributor" --scope "$STORAGE_ACCOUNT_ID" 1>/dev/null || true
  az role assignment create --assignee "$SP_OBJECT_ID" --role "Storage Account Key Operator Service Role" --scope "$STORAGE_ACCOUNT_ID" 1>/dev/null || true
  az role assignment create --assignee "$SP_OBJECT_ID" --role "Reader" --scope "$STORAGE_ACCOUNT_ID" 1>/dev/null || true

  if [[ -n "$STORAGE_CONTAINER_NAME" ]]; then
    info "Ensuring blob container '$STORAGE_CONTAINER_NAME'..."
    local key
    key="$(az storage account keys list --account-name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query '[0].value' -o tsv)"
    az storage container create --name "$STORAGE_CONTAINER_NAME" --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$key" 1>/dev/null || true
  fi
}

###############################################################################
# ensure_kv: Create or reuse Key Vault; enable RBAC and assign SPN; seed secrets.
###############################################################################
ensure_kv() {
  [[ -z "$KV_NAME" ]] && return
  [[ -z "$LOCATION" ]] && die "Need --location to create Key Vault."

  if ! az keyvault show -n "$KV_NAME" -g "$RESOURCE_GROUP" >/dev/null 2>&1; then
    info "Creating Key Vault '$KV_NAME' in $LOCATION (RBAC enabled)..."
    az keyvault create \
      --name "$KV_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --enable-rbac-authorization true \
      --public-network-access Enabled 1>/dev/null
  else
    info "Key Vault '$KV_NAME' exists."
  fi

  KV_ID="$(az keyvault show -n "$KV_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)"

  info "Granting SPN Key Vault Secrets User on the vault..."
  az role assignment create \
    --assignee "$SP_OBJECT_ID" \
    --role "Key Vault Secrets User" \
    --scope "$KV_ID" 1>/dev/null || true

  # Seed secrets if provided
  if (( ${#KV_SECRETS[@]} > 0 )); then
    for kv in "${KV_SECRETS[@]}"; do
      local name value
      name="${kv%%=*}"; value="${kv#*=}"
      if [[ -z "$name" || -z "$value" ]]; then
        warn "Skipping malformed --kv-secret entry: '$kv' (expected NAME=VALUE)"
        continue
      fi
      info "Setting secret '$name' in Key Vault '$KV_NAME'..."
      az keyvault secret set --vault-name "$KV_NAME" --name "$name" --value "$value" 1>/dev/null
    done
  fi
}

###############################################################################
# ensure_identity: Create or reuse managed identity; assign storage role.
###############################################################################
ensure_identity() {
  [[ -z "$IDENTITY_NAME" ]] && return
  if ! az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    [[ -z "$LOCATION" ]] && die "Need --location to create identity."
    info "Creating Managed Identity '$IDENTITY_NAME'..."
    az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --tags project="$TAG_PROJECT" 1>/dev/null
  else
    info "Managed Identity '$IDENTITY_NAME' exists."
  fi
  ID_CLIENT_ID="$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query clientId -o tsv)"
  ID_PRINCIPAL_ID="$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query principalId -o tsv)"

  if [[ -n "${STORAGE_ACCOUNT_ID:-}" ]]; then
    info "Assigning Storage Blob Data Contributor to identity."
    az role assignment create --assignee "$ID_PRINCIPAL_ID" --role "Storage Blob Data Contributor" --scope "$STORAGE_ACCOUNT_ID" 1>/dev/null || true
  fi
}

###############################################################################
# emit_env: Write environment variable exports to a file.
###############################################################################
emit_env() {
  [[ -z "$EMIT_ENV_FILE" ]] && return
  info "Writing environment exports to '$EMIT_ENV_FILE'."
  {
    echo "# acido environment exports"
    echo "export AZURE_SUBSCRIPTION_ID=\"$SUBSCRIPTION_ID\""
    echo "export AZURE_RESOURCE_GROUP=\"$RESOURCE_GROUP\""
    echo "export AZURE_CLIENT_ID=\"$APP_ID\""
    echo "export AZURE_TENANT_ID=\"$(az account show --query tenantId -o tsv)\""
    
    # ACR credentials
    if [[ -n "$ACR_NAME" ]]; then
      echo "export AZURE_ACR_NAME=\"$ACR_NAME\""
      echo "export IMAGE_REGISTRY_SERVER=\"${ACR_NAME}.azurecr.io\""
      
      # Get ACR credentials
      local acr_username acr_password
      acr_username="$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query username -o tsv 2>/dev/null || echo "$ACR_NAME")"
      acr_password="$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query 'passwords[0].value' -o tsv 2>/dev/null || echo "")"
      
      echo "export IMAGE_REGISTRY_USERNAME=\"$acr_username\""
      [[ -n "$acr_password" ]] && echo "export IMAGE_REGISTRY_PASSWORD=\"$acr_password\""
    fi
    
    # Storage Account details
    if [[ -n "$STORAGE_ACCOUNT_NAME" ]]; then
      echo "export STORAGE_ACCOUNT_NAME=\"$STORAGE_ACCOUNT_NAME\""
      
      # Get storage account key
      local storage_key
      storage_key="$(az storage account keys list --account-name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query '[0].value' -o tsv 2>/dev/null || echo "")"
      [[ -n "$storage_key" ]] && echo "export STORAGE_ACCOUNT_KEY=\"$storage_key\""
    fi
    
    [[ -n "$STORAGE_CONTAINER_NAME" ]] && echo "export STORAGE_CONTAINER_NAME=\"$STORAGE_CONTAINER_NAME\""
    [[ -n "$ID_CLIENT_ID" ]] && echo "export MANAGED_IDENTITY_CLIENT_ID=\"$ID_CLIENT_ID\""
    [[ -n "$KV_NAME" ]] && echo "export KEY_VAULT_NAME=\"$KV_NAME\""
    
    if $GENERATE_CLIENT_SECRET && [[ -n "${GENERATED_CLIENT_SECRET:-}" ]]; then
      echo "export AZURE_CLIENT_SECRET=\"$GENERATED_CLIENT_SECRET\""
    fi
  } > "$EMIT_ENV_FILE"
}

###############################################################################
# summary: Print installation summary.
###############################################################################
summary() {
  echo ""
  echo "================= INSTALL SUMMARY ================="
  echo "Subscription:        $SUBSCRIPTION_ID"
  echo "Resource Group:      $RESOURCE_GROUP"
  echo "Location:            ${LOCATION:-'(none)'}"
  echo "SP Name:             $SP_NAME"
  echo "SP AppId:            $APP_ID"
  echo "SP ObjectId:         $SP_OBJECT_ID"
  echo "Privilege Model:     $([[ $LEAST_PRIVILEGE == true ]] && echo 'Least Privilege' || echo 'Contributor')"
  echo "ACR Name:            ${ACR_NAME:-'(none)'}"
  echo "Storage Account:     ${STORAGE_ACCOUNT_NAME:-'(none)'}"
  echo "Blob Container:      ${STORAGE_CONTAINER_NAME:-'(none)'}"
  echo "Key Vault:           ${KV_NAME:-'(none)'}"
  echo "Managed Identity:    ${IDENTITY_NAME:-'(none)'}"
  echo "Identity Client ID:  ${ID_CLIENT_ID:-'(n/a)'}"
  echo "Env File:            ${EMIT_ENV_FILE:-'(none)'}"
  if $GENERATE_CLIENT_SECRET; then
    echo "Client Secret Gen:   $([[ -n "${GENERATED_CLIENT_SECRET:-}" ]] && echo 'yes' || echo 'failed')"
    $SHOW_SECRET || echo "Secret Displayed:    no (use --show-secret)"
  else
    echo "Client Secret Gen:   skipped (--no-client-secret)"
  fi
  if (( ${#KV_SECRETS[@]} > 0 )); then
    echo "KV Secrets Seeded:   ${#KV_SECRETS[@]}"
  fi
  echo "===================================================="
  echo ""
  note "Next: source the env file (if created) or export variables, then run acido."
}

###############################################################################
# main: Orchestrate install steps.
###############################################################################
main() {
  parse_args "$@"
  validate_inputs
  ensure_subscription
  ensure_rg
  ensure_sp
  assign_roles
  ensure_acr
  ensure_storage
  ensure_kv
  ensure_identity
  emit_env
  summary
}

main "$@"
