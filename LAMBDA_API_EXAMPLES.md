# Lambda Handler API Examples

This document provides examples of using the lambda_handler API to control all acido operations via JSON.

## Overview

The lambda_handler now supports the following operations via JSON:
- `fleet`: Create multiple container instances for distributed scanning
- `run`: Create a single ephemeral instance with auto-cleanup
- `ls`: List all container instances
- `rm`: Remove container instances

## Operation Examples

### 1. Fleet Operation (Distributed Scanning)

Create multiple container instances for distributed scanning:

```json
{
  "operation": "fleet",
  "image": "kali-rolling",
  "targets": ["merabytes.com", "uber.com", "facebook.com"],
  "task": "nmap -iL input -p 0-1000",
  "fleet_name": "scan-fleet",
  "num_instances": 3,
  "rm_when_done": true
}
```

### 2. Run Operation (Single Ephemeral Instance)

Create a single ephemeral instance with auto-cleanup:

```json
{
  "operation": "run",
  "name": "github-runner-01",
  "image": "github-runner",
  "task": "./run.sh",
  "duration": 900,
  "cleanup": true
}
```

### 3. List Operation

List all container instances:

```json
{
  "operation": "ls"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "operation": "ls",
    "instances": [
      {
        "container_group": "fleet-1",
        "containers": ["fleet-1-01", "fleet-1-02"]
      }
    ]
  }
}
```

### 4. Remove Operation

Remove container instances by name or pattern:

```json
{
  "operation": "rm",
  "name": "fleet-1"
}
```

Remove multiple instances using wildcards:

```json
{
  "operation": "rm",
  "name": "scan-fleet*"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "operation": "rm",
    "result": {
      "removed": "fleet-1"
    }
  }
}
```

### 5. IP Create Operation

Create a new IPv4 address and network profile:

```json
{
  "operation": "ip_create",
  "name": "pentest-ip"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "operation": "ip_create",
    "result": {
      "created": "pentest-ip"
    }
  }
}
```

### 6. IP List Operation

List all IPv4 addresses:

```json
{
  "operation": "ip_ls"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "operation": "ip_ls",
    "ip_addresses": [
      {
        "name": "pentest-ip",
        "ip_address": "20.123.45.67"
      }
    ]
  }
}
```

### 7. IP Remove Operation

Remove IPv4 address and network profile:

```json
{
  "operation": "ip_rm",
  "name": "pentest-ip"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "operation": "ip_rm",
    "result": {
      "removed": "pentest-ip",
      "success": true
    }
  }
}
```

## Using with API Gateway

When using with API Gateway, wrap the payload in a `body` field:

```json
{
  "body": {
    "operation": "ls"
  }
}
```

## CLI Equivalents

| Lambda API | CLI Command |
|------------|-------------|
| `{"operation": "fleet", ...}` | `acido fleet <fleet-name> -im <image> -t <task> ...` |
| `{"operation": "run", ...}` | `acido run <name> -im <image> -t <task> ...` |
| `{"operation": "ls"}` | `acido ls` |
| `{"operation": "rm", "name": "..."}` | `acido rm <name>` |
| `{"operation": "ip_create", "name": "..."}` | `acido ip create <name>` |
| `{"operation": "ip_ls"}` | `acido ip ls` |
| `{"operation": "ip_rm", "name": "..."}` | `acido ip rm <name>` |

## Error Responses

All operations return error responses with a 400 or 500 status code:

```json
{
  "statusCode": 400,
  "body": {
    "error": "Missing required fields for rm operation: name"
  }
}
```

## Environment Variables

All operations require the following environment variables:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_RESOURCE_GROUP`
- `IMAGE_REGISTRY_SERVER`
- `IMAGE_REGISTRY_USERNAME`
- `IMAGE_REGISTRY_PASSWORD`
- `STORAGE_ACCOUNT_NAME`
- `STORAGE_ACCOUNT_KEY` (optional)
- `MANAGED_IDENTITY_ID` (optional)
- `MANAGED_IDENTITY_CLIENT_ID` (optional)
