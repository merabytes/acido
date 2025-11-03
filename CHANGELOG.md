# Changelog

All notable changes to acido will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.44.0] - 2025-11-03

### Added
- **New `acido create` options** for enhanced Dockerfile generation:
  - `--break-system-packages`: Use `--break-system-packages` flag when installing acido with pip (for externally managed Python environments per PEP 668)
  - `--entrypoint`: Override the default ENTRYPOINT in the generated Dockerfile
  - `--cmd`: Override the default CMD in the generated Dockerfile
  - Fixes CI nuclei test failures on images with externally managed Python

### Changed
- **Simplified Input Handling**: Fleet operations now use environment variables instead of chained commands
  - Input file UUID is now passed via `ACIDO_INPUT_UUID` environment variable
  - `acido -sh` automatically downloads input when environment variable is detected
  - Eliminates the need for chained commands like `acido -d <uuid> && acido -sh '<command>'`
  - Commands are now cleaner: just `acido -sh '<command>'`
  - Reduces overhead and improves code maintainability
- **Version Management**: Updated from 0.43.0 to 0.44.0
- **CI Workflow**: Added test for `--root` flag with nuclei image

### Technical Details
- Modified `InstanceManager.deploy()` to set `ACIDO_INPUT_UUID` environment variable
- Modified `Acido.save_output()` to auto-download input when environment variable is present
- Modified `_generate_dockerfile()` to support new customization options
- Backward compatible: `-d` flag still works when called manually

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
