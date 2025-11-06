# Multi-Region Support Examples

## CLI Examples

### Fleet command with multiple regions

```bash
# Deploy 100 containers across 3 regions randomly
acido fleet nuclei-scan \
  -n 100 \
  -im nuclei \
  -t 'nuclei -list input' \
  -i targets.txt \
  --region westeurope \
  --region eastus \
  --region westus2
```

### Fleet command with all 48 regions for maximum scale

```bash
# Deploy 1000 containers across all Azure regions
acido fleet massive-scan \
  -n 1000 \
  -im nuclei \
  -t 'nuclei -list input' \
  -i targets.txt \
  --region australiacentral \
  --region australiaeast \
  --region australiasoutheast \
  --region austriaeast \
  --region belgiumcentral \
  --region brazilsouth \
  --region canadacentral \
  --region canadaeast \
  --region centralindia \
  --region centralus \
  --region chilecentral \
  --region eastasia \
  --region eastus \
  --region eastus2 \
  --region francecentral \
  --region germanywestcentral \
  --region indonesiacentral \
  --region israelcentral \
  --region italynorth \
  --region japaneast \
  --region japanwest \
  --region jioindiawest \
  --region koreacentral \
  --region koreasouth \
  --region malaysiawest \
  --region mexicocentral \
  --region newzealandnorth \
  --region northcentralus \
  --region northeurope \
  --region norwayeast \
  --region polandcentral \
  --region qatarcentral \
  --region southafricanorth \
  --region southcentralus \
  --region southeastasia \
  --region southindia \
  --region spaincentral \
  --region swedencentral \
  --region switzerlandnorth \
  --region uaenorth \
  --region uksouth \
  --region ukwest \
  --region westcentralus \
  --region westeurope \
  --region westindia \
  --region westus \
  --region westus2 \
  --region westus3
```

### Run command with multiple regions

```bash
# Deploy ephemeral runner across 2 regions (randomly selected)
acido run github-runner-01 \
  -im github-runner \
  -t './run.sh' \
  -d 900 \
  --region westeurope \
  --region eastus
```

## Lambda Examples

### Fleet operation with multiple regions

```json
{
  "operation": "fleet",
  "image": "nuclei",
  "targets": ["merabytes.com", "uber.com"],
  "task": "nuclei -list input",
  "regions": ["westeurope", "eastus", "westus2"]
}
```

### Fleet operation with single region (backward compatible)

```json
{
  "operation": "fleet",
  "image": "nuclei",
  "targets": ["merabytes.com"],
  "task": "nuclei -list input",
  "region": "westeurope"
}
```

### Run operation with multiple regions

```json
{
  "operation": "run",
  "name": "github-runner-01",
  "image": "github-runner",
  "task": "./run.sh",
  "duration": 900,
  "regions": ["westeurope", "eastus"]
}
```

## How It Works

1. **Random Distribution**: Instances are randomly distributed across the provided regions
2. **Container Groups**: Each container group (max 10 instances per group) is deployed to a randomly selected region
3. **Regional Limits**: Azure limits each region to ~20 container instances, so using multiple regions allows scaling to 1000+ containers
4. **Backward Compatibility**: Single region strings are automatically converted to lists internally

## Region List

All 48 supported Azure regions:

- australiacentral, australiaeast, australiasoutheast
- austriaeast, belgiumcentral, brazilsouth, canadacentral, canadaeast
- centralindia, centralus, chilecentral, eastasia, eastus, eastus2
- francecentral, germanywestcentral, indonesiacentral, israelcentral
- italynorth, japaneast, japanwest, jioindiawest, koreacentral, koreasouth
- malaysiawest, mexicocentral, newzealandnorth, northcentralus, northeurope
- norwayeast, polandcentral, qatarcentral, southafricanorth, southcentralus
- southeastasia, southindia, spaincentral, swedencentral, switzerlandnorth
- uaenorth, uksouth, ukwest, westcentralus, westeurope, westindia, westus
- westus2, westus3
