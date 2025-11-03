# Changelog

All notable changes to acido will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.44.0] - 2025-11-03

### Added
- **Pre-built Binary Support**: Lightweight image creation using standalone acido binaries
  - New CI/CD workflow (`build-binaries.yml`) to build binaries for Ubuntu and Alpine Linux
  - Binaries published to GitHub Releases on version tags
  - Uses PyInstaller to create single-file executables
  - Includes SHA256 checksums for verification
  - Default approach for `acido create` (no Python dependencies in images)
- **New `acido create` options** for enhanced Dockerfile generation:
  - `--use-venv`: Use Python virtual environment instead of binary (larger but more flexible)
  - `--entrypoint`: Override the default ENTRYPOINT in the generated Dockerfile
  - `--cmd`: Override the default CMD in the generated Dockerfile
  - `--break-system-packages`: [Deprecated] Use `--use-venv` instead

### Changed
- **Default installation method**: Now uses pre-built binaries (lightweight)
  - Downloads binary via wget (much smaller images)
  - No Python interpreter or pip needed in final image
  - Fallback to virtual environment approach with `--use-venv` flag
- **Virtual Environment for acido installation** (when using `--use-venv`):
  - Creates `/opt/acido-venv` virtual environment
  - Installs acido inside the venv to avoid PEP 668 conflicts
  - Automatically adds venv to PATH so acido CLI is available
  - Works cleanly with all base images including Alpine, Debian, and RHEL
- **Simplified Input Handling**: Fleet operations now use environment variables instead of chained commands
  - Input file UUID is now passed via `ACIDO_INPUT_UUID` environment variable
  - `acido -sh` automatically downloads input when environment variable is detected
  - Eliminates the need for chained commands like `acido -d <uuid> && acido -sh '<command>'`
  - Commands are now cleaner: just `acido -sh '<command>'`
  - Reduces overhead and improves code maintainability
- **Version Management**: Updated from 0.43.0 to 0.44.0
- **CI Workflow**: Added test for `--root` flag with nuclei image

### Technical Details
- Added `_generate_dockerfile_with_binary()` method for binary-based Dockerfile generation
- Modified `InstanceManager.deploy()` to set `ACIDO_INPUT_UUID` environment variable
- Modified `Acido.save_output()` to auto-download input when environment variable is present
- Binary approach creates significantly smaller images (no Python dependencies)
- Backward compatible: `--use-venv` and `--break-system-packages` still work

## [0.42.0] - 2025-01-03

### Added
- **GitHub Repository Support**: Build acido-compatible Docker images directly from GitHub repositories using `git+https://` syntax
  - Support for branches, tags, and commit SHAs: `git+https://github.com/user/repo@ref`
  - Automatic Dockerfile detection in repository root
  - Tag sanitization for Docker compatibility
  - Example: `acido create git+https://github.com/projectdiscovery/nuclei`
- **CI/CD Improvements**:
  - New `release.yml` workflow for building release artifacts with checksums
  - GitHub URL testing in CI pipeline
  - Version consistency checks across all files
  - Automatic GitHub releases on version tags
- **CHANGELOG.md**: Added changelog to track version history

### Changed
- **Secrets Lambda**: Secrets are no longer deleted on wrong password attempts, allowing users to retry
  - Only deleted on successful retrieval with correct password
  - Improves user experience and prevents accidental data loss
- **Version Management**: Updated from 0.41.1 to 0.42.0
  - Consistent version numbers across `setup.py`, `decoration.py`, and `lambda_handler_secrets.py`
- **Publish Workflow**: Now triggers on version tags (`v*.*.*`) instead of every push to main

### Fixed
- Secret deletion bug where entering wrong password would permanently delete the secret
- Version consistency across different files

## [0.41.1] - Previous Release

### Features from Previous Releases
- AWS Lambda support for distributed scanning
- Secrets sharing service (OneTimeSecret-like functionality)
- CloudFlare Turnstile integration for bot protection
- Password-encrypted secrets with AES-256
- Azure Container Instances orchestration
- Fleet management for distributed security scanning
- Support for security tools: Nuclei, Nmap, Masscan, Kali Linux, etc.
- Docker-like CLI with subcommands (create, fleet, ls, rm, exec)

---

## Version Numbering

acido follows [Semantic Versioning](https://semver.org/):
- **MAJOR** version (0.x.x): Incompatible API changes
- **MINOR** version (x.X.x): New functionality in backward-compatible manner
- **PATCH** version (x.x.X): Backward-compatible bug fixes

## Release Process

1. Update version in:
   - `acido/utils/decoration.py` (`__version__`)
   - `setup.py` (`version=`)
   - `lambda_handler_secrets.py` (`'version':`)
2. Update CHANGELOG.md with release notes
3. Commit changes: `git commit -m "Bump version to X.Y.Z"`
4. Create and push tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. GitHub Actions automatically:
   - Builds distribution packages
   - Creates GitHub release with artifacts
   - Publishes to PyPI

[0.44.0]: https://github.com/merabytes/acido/releases/tag/v0.44.0
[0.42.0]: https://github.com/merabytes/acido/releases/tag/v0.42.0
[0.41.1]: https://github.com/merabytes/acido/releases/tag/v0.41.1
