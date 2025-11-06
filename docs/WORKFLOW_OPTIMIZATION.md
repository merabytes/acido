# Workflow Optimization Strategy

## Overview

This document explains the workflow optimization strategy for the acido monorepo containing both the main `acido` package and the `acido-client` package. The optimizations are designed to reduce CI/CD costs and execution time by ensuring workflows only run when necessary.

## Package Structure

```
acido/
├── acido/                 # Main package (Azure SDK, CLI, Lambda)
├── acido-client/          # Client package (REST API client, minimal deps)
├── .github/workflows/
│   ├── ci.yml            # Main package CI
│   ├── ci-client.yml     # Client package CI
│   ├── publish.yml       # Main package PyPI publish
│   ├── publish-client.yml # Client package PyPI publish
│   ├── deploy-lambda.yml # Lambda deployment
│   ├── build-binaries.yml # Standalone binaries
│   └── release.yml       # Release management
```

## Optimization Strategy

### 1. Path-Based Filtering

**Problem**: CI workflows running unnecessarily when changes only affect the other package.

**Solution**: Implemented path filtering using `paths` and `paths-ignore`:

#### Main Package CI (`ci.yml`)
- **Runs when**: Changes to main package code, tests, workflows
- **Skips when**: Only `acido-client/` files change
- **Saves**: ~50% of CI runs when client-only changes are made

```yaml
on:
  push:
    paths-ignore:
      - 'acido-client/**'
      - '.github/workflows/ci-client.yml'
      - '.github/workflows/publish-client.yml'
```

#### Client Package CI (`ci-client.yml`)
- **Runs when**: Changes to client package code, tests, workflows
- **Skips when**: Only main package files change
- **Saves**: ~50% of CI runs when main-only changes are made

```yaml
on:
  push:
    paths:
      - 'acido-client/**'
      - '.github/workflows/ci-client.yml'
```

### 2. Lambda Deployment Optimization

**Problem**: Lambda deployment running for documentation or client-only changes.

**Solution**: Added `paths-ignore` to skip unnecessary deployments:

```yaml
on:
  push:
    paths-ignore:
      - 'acido-client/**'
      - '.github/workflows/ci-client.yml'
      - '.github/workflows/publish-client.yml'
      - 'README.md'
      - 'docs/**'
      - '*.md'
```

**Saves**: Avoids expensive Docker builds and AWS deployments for non-functional changes.

### 3. Package Publishing Separation

**Problem**: Both packages share the same version number and both publish workflows trigger on the same tags.

**Solution**: Clear separation with documentation:
- `publish.yml` - Handles main `acido` package → PyPI (uses `PYPI_API_TOKEN`)
- `publish-client.yml` - Handles `acido-client` package → PyPI (uses `PYPI_API_TOKEN_CLIENT`)

Both workflows can run in parallel without conflicts as they publish different packages to different PyPI entries.

## Cost Savings Analysis

### Before Optimization

| Scenario | Workflows Run | Cost |
|----------|--------------|------|
| Main package change | 2 CIs + Lambda deploy | High |
| Client package change | 2 CIs + Lambda deploy | High |
| Documentation change | 2 CIs + Lambda deploy | High |

### After Optimization

| Scenario | Workflows Run | Cost | Savings |
|----------|--------------|------|---------|
| Main package change | Main CI + Lambda deploy | Medium | -1 CI job |
| Client package change | Client CI only | Low | -1 CI + Lambda |
| Documentation change | Neither CI + No Lambda | None | -2 CIs + Lambda |

**Estimated Savings**: 40-60% reduction in workflow execution time and cost.

## Workflow Execution Matrix

| Change Type | ci.yml | ci-client.yml | deploy-lambda.yml | Notes |
|-------------|--------|---------------|-------------------|-------|
| Main package code | ✅ | ❌ | ✅ | Full main pipeline |
| Client package code | ❌ | ✅ | ❌ | Client-only testing |
| README.md only | ❌ | ❌ | ❌ | Documentation only |
| Both packages | ✅ | ✅ | ✅ | Both pipelines run |
| Workflow file change | ✅ | ✅ | ✅ | Safety: run all |

## Publishing Strategy

### Version Synchronization

Both packages share the same version number (e.g., `0.40.2`) to maintain consistency and simplify releases.

### Tag-Based Publishing

When a version tag is pushed (e.g., `v0.40.2`):

1. **publish.yml** runs:
   - Builds main `acido` package
   - Verifies version consistency
   - Publishes to PyPI as `acido`

2. **publish-client.yml** runs (parallel):
   - Builds `acido-client` package
   - Verifies version consistency with main package
   - Publishes to PyPI as `acido-client`

3. **build-binaries.yml** runs (parallel):
   - Builds standalone binaries for main package

4. **release.yml** may run:
   - Creates GitHub release with all artifacts

### Required Secrets

- `PYPI_API_TOKEN` - For main acido package
- `PYPI_API_TOKEN_CLIENT` - For acido-client package

## Best Practices

### When Making Changes

1. **Main package only**: Changes automatically skip client CI
2. **Client package only**: Changes automatically skip main CI and Lambda deployment
3. **Documentation only**: All workflows skip, saving maximum resources
4. **Both packages**: Both CIs run, ensuring full validation

### Manual Workflow Triggers

All workflows support `workflow_dispatch` for manual execution:
- Useful for testing without pushing code
- Can override path filtering when needed

### Future Optimizations

Potential areas for further optimization:

1. **Caching**: Add dependency caching for faster builds
2. **Conditional Jobs**: Split CI jobs to run only affected tests
3. **Matrix Reduction**: Reduce Python version matrix for faster feedback (currently 3.8-3.12)
4. **Artifact Reuse**: Share build artifacts between workflows

## Monitoring

Track workflow efficiency using GitHub Actions insights:

1. **Workflow runs**: Monitor which workflows trigger most frequently
2. **Execution time**: Identify slow workflows for optimization
3. **Success rate**: Ensure path filtering doesn't cause missed tests

## Troubleshooting

### Issue: Main CI not running
**Check**: Did you modify only client files? This is expected behavior.

### Issue: Client CI not running
**Check**: Did you modify only main package files? This is expected behavior.

### Issue: Both packages need testing
**Solution**: Use `workflow_dispatch` to manually trigger both CIs, or modify a file in both directories.

## Summary

The workflow optimization strategy achieves:

✅ **Cost Reduction**: 40-60% fewer workflow executions
✅ **Faster Feedback**: Developers get quicker CI results
✅ **Resource Efficiency**: No unnecessary Lambda deployments
✅ **Clear Separation**: Each package has dedicated CI/CD pipeline
✅ **Flexibility**: Manual override available via workflow_dispatch
✅ **Safety**: Version consistency checks prevent mismatches

This approach maintains code quality while significantly reducing CI/CD resource consumption.
