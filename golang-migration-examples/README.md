# Acido - Golang Migration Examples

This directory contains example Go code demonstrating the proposed migration of Acido from Python to Golang. These files showcase the structure, patterns, and implementation approach for the Go version.

## Files Overview

### Build & Configuration

- **`go.mod.example`** - Go module dependencies
  - Shows all required Azure SDK packages
  - CLI framework (Cobra)
  - Utility libraries

- **`Makefile.example`** - Build automation
  - Cross-compilation for multiple platforms
  - Testing, linting, coverage
  - Lambda handler builds
  - Docker image creation

### Application Structure (Coming Soon)

Additional example files will be created for:
- Main CLI entry point
- Fleet command implementation  
- Azure Container Instances manager
- And more...

## How to Use These Examples

### 1. Study the Structure

Review the files to understand:
- Go project layout (`cmd/`, `internal/`, `pkg/`)
- Dependency management with `go.mod`
- Build automation with Makefile
- Azure SDK integration patterns

### 2. Use as Migration Templates

When migrating specific components:
1. Reference the corresponding example file
2. Adapt the patterns to your needs
3. Maintain consistency with Go idioms

### 3. Test the Patterns

You can copy these examples to a new Go project:

```bash
# Create new project
mkdir acido-go && cd acido-go

# Copy and rename example files
cp golang-migration-examples/go.mod.example go.mod
cp golang-migration-examples/Makefile.example Makefile

# Create directory structure
mkdir -p cmd/acido internal/cli internal/azure

# Download dependencies
go mod tidy

# Build (after implementing components)
make build
```

## Key Build Commands

From the Makefile:

```bash
make help           # Show all available commands
make build          # Build for current platform
make build-all      # Cross-compile for all platforms
make build-lambda   # Build Lambda handlers
make test           # Run unit tests
make test-coverage  # Generate coverage report
make lint           # Run linters
make fmt            # Format code
make clean          # Clean artifacts
make install        # Install to GOPATH
```

## Dependency Overview

### Azure SDK (Official Microsoft Go SDK)
```
github.com/Azure/azure-sdk-for-go/sdk/azidentity           # Auth
github.com/Azure/azure-sdk-for-go/sdk/azcore               # Core
github.com/Azure/azure-sdk-for-go/sdk/storage/azblob       # Blob Storage
github.com/Azure/azure-sdk-for-go/sdk/security/keyvault/*  # KeyVault
```

### CLI Framework
```
github.com/spf13/cobra      # Command structure (kubectl/docker pattern)
github.com/fatih/color      # Colored output
github.com/AlecAivazis/survey/v2  # Interactive prompts
github.com/schollz/progressbar/v3 # Progress indicators
```

### AWS Lambda
```
github.com/aws/aws-lambda-go  # Official AWS runtime
```

### Utilities
```
github.com/google/uuid       # UUID generation
github.com/gorilla/websocket # WebSocket support
```

## Next Steps

After reviewing these examples:

1. **Read** `GOLANG_MIGRATION_ANALYSIS.md` for complete migration strategy
2. **Set up** development environment with Go 1.21+
3. **Start** with Phase 1 (Azure utilities) 
4. **Test** thoroughly with mocks and integration tests
5. **Deploy** gradually with parallel Python/Go versions

## Resources

- [Azure SDK for Go](https://github.com/Azure/azure-sdk-for-go)
- [Cobra CLI Framework](https://github.com/spf13/cobra)
- [Go by Example](https://gobyexample.com/)
- [Effective Go](https://go.dev/doc/effective_go)

## Questions?

Refer to the main migration document (`GOLANG_MIGRATION_ANALYSIS.md`) for detailed explanations, challenges, and solutions.
