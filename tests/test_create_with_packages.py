"""
Unit tests for acido create command with package installation.

Tests the create_acido_image functionality with --install flag.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import tempfile
from acido.utils.decoration import BANNER, __version__

# Mock sys.argv to prevent argparse from processing test args
_original_argv = sys.argv
sys.argv = ['test']

# Set required environment variables for tests
os.environ['AZURE_TENANT_ID'] = 'test-tenant-id'
os.environ['AZURE_CLIENT_ID'] = 'test-client-id'
os.environ['AZURE_CLIENT_SECRET'] = 'test-secret'
os.environ['AZURE_RESOURCE_GROUP'] = 'test-rg'
os.environ['IMAGE_REGISTRY_SERVER'] = 'test.azurecr.io'
os.environ['IMAGE_REGISTRY_USERNAME'] = 'test-user'
os.environ['IMAGE_REGISTRY_PASSWORD'] = 'test-pass'
os.environ['STORAGE_ACCOUNT_NAME'] = 'testaccount'
os.environ['STORAGE_ACCOUNT_KEY'] = 'test-storage-key'
os.environ['MANAGED_IDENTITY_ID'] = '/subscriptions/test-sub/resourcegroups/test-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-identity'
os.environ['MANAGED_IDENTITY_CLIENT_ID'] = 'test-managed-identity-client-id'

try:
    from acido.cli import Acido
finally:
    # Restore original argv
    sys.argv = _original_argv


class TestCreateWithPackages(unittest.TestCase):
    """Test cases for create command with package installation."""

    def setUp(self):
        """Set up test fixtures."""
        pass

    def test_validate_package_name_valid(self):
        """Test package name validation with valid names."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        # Valid package names
        self.assertTrue(acido._validate_package_name('nmap'))
        self.assertTrue(acido._validate_package_name('masscan'))
        self.assertTrue(acido._validate_package_name('python3-pip'))
        self.assertTrue(acido._validate_package_name('gcc-c++'))
        self.assertTrue(acido._validate_package_name('lib.test_1.0'))
        self.assertTrue(acido._validate_package_name('package_name'))

    def test_validate_package_name_invalid(self):
        """Test package name validation with invalid names."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        # Invalid package names
        self.assertFalse(acido._validate_package_name('nmap; rm -rf /'))
        self.assertFalse(acido._validate_package_name('pkg && evil'))
        self.assertFalse(acido._validate_package_name('pkg | nc'))
        self.assertFalse(acido._validate_package_name('pkg`whoami`'))
        self.assertFalse(acido._validate_package_name('pkg$HOME'))
        self.assertFalse(acido._validate_package_name(''))
        self.assertFalse(acido._validate_package_name('-invalid'))
        self.assertFalse(acido._validate_package_name('.invalid'))

    def test_generate_dockerfile_with_packages_debian(self):
        """Test Dockerfile generation with packages for Debian."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap', 'masscan']
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages)
        
        # Check that packages are installed before acido
        self.assertIn('FROM ubuntu:20.04', dockerfile)
        self.assertIn('# Install custom packages', dockerfile)
        self.assertIn('apt-get update && apt-get install -y nmap masscan', dockerfile)
        self.assertIn('pip install --upgrade pip', dockerfile)
        self.assertIn(f'pip install acido=={__version__}', dockerfile)
        
        # Verify installation order: Python deps, then custom packages, then acido
        python_idx = dockerfile.find('python3-pip build-essential')
        custom_idx = dockerfile.find('# Install custom packages')
        acido_idx = dockerfile.find(f'pip install acido=={__version__}')
        
        self.assertLess(python_idx, custom_idx)
        self.assertLess(custom_idx, acido_idx)

    def test_generate_dockerfile_with_packages_alpine(self):
        """Test Dockerfile generation with packages for Alpine."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'alpine:3.14'
        distro_info = {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
        packages = ['nmap', 'masscan']
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages)
        
        # Check that packages are installed before acido
        self.assertIn('FROM alpine:3.14', dockerfile)
        self.assertIn('# Install custom packages', dockerfile)
        self.assertIn('apk update && apk add --no-cache nmap masscan', dockerfile)
        self.assertIn('pip install --upgrade pip', dockerfile)
        self.assertIn(f'pip install acido=={__version__}', dockerfile)

    def test_generate_dockerfile_kali_auto_install(self):
        """Test automatic kali-linux-large installation for kali-rolling images."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'kalilinux/kali-rolling'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap']
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages)
        
        # Check that kali-linux-large is auto-installed
        self.assertIn('kali-linux-large', dockerfile)
        self.assertIn('nmap', dockerfile)
        # kali-linux-large should come before nmap (inserted at position 0)
        self.assertLess(dockerfile.find('kali-linux-large'), dockerfile.find('nmap'))

    def test_generate_dockerfile_kali_no_duplicate(self):
        """Test that kali-linux-large is not duplicated if already in package list."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'kalilinux/kali-rolling'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['kali-linux-large', 'nmap']
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages)
        
        # Count occurrences of kali-linux-large - should only appear once
        self.assertEqual(dockerfile.count('kali-linux-large'), 1)

    def test_generate_dockerfile_no_packages(self):
        """Test Dockerfile generation without additional packages."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, None)
        
        # Check that no custom package installation is present
        self.assertNotIn('# Install custom packages', dockerfile)
        self.assertIn('pip install --upgrade pip', dockerfile)
        self.assertIn(f'pip install acido=={__version__}', dockerfile)

    def test_generate_dockerfile_invalid_packages_filtered(self):
        """Test that invalid package names are filtered out."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap', 'evil; rm -rf /', 'masscan']
        
        with patch('builtins.print') as mock_print:
            dockerfile = acido._generate_dockerfile(base_image, distro_info, packages)
        
        # Check that only valid packages are installed
        self.assertIn('nmap', dockerfile)
        self.assertIn('masscan', dockerfile)
        # Check that the malicious command wasn't added as a package
        self.assertNotIn('install -y nmap evil', dockerfile)
        self.assertNotIn('install -y evil', dockerfile)

    def test_generate_dockerfile_with_update_debian(self):
        """Test Dockerfile generation with default package update for Debian."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap']
        
        # Default behavior: update packages (no_update=False)
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False)
        
        # Check that apt-get update is included
        self.assertIn('apt-get update && apt-get install -y nmap', dockerfile)

    def test_generate_dockerfile_without_update_debian(self):
        """Test Dockerfile generation without package update for Debian."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap']
        
        # With --no-update flag (no_update=True)
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=True)
        
        # Check that apt-get update is NOT included in custom packages section
        self.assertNotIn('apt-get update && apt-get install -y nmap', dockerfile)
        # But should have apt-get install without update
        self.assertIn('apt-get install -y nmap', dockerfile)

    def test_generate_dockerfile_default_entrypoint(self):
        """Test that the default entrypoint is set to /opt/acido-venv/bin/acido."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, None)
        
        # Check that the default entrypoint is set to the venv acido binary
        self.assertIn('ENTRYPOINT ["/opt/acido-venv/bin/acido"]', dockerfile)
        self.assertIn('CMD ["sleep", "infinity"]', dockerfile)

    def test_generate_dockerfile_custom_entrypoint(self):
        """Test that custom entrypoint overrides the default."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        
        dockerfile = acido._generate_dockerfile(base_image, distro_info, None, custom_entrypoint='/bin/bash')
        
        # Check that the custom entrypoint is used
        self.assertIn('ENTRYPOINT ["/bin/bash"]', dockerfile)
        self.assertNotIn('ENTRYPOINT ["/opt/acido-venv/bin/acido"]', dockerfile)

    def test_generate_dockerfile_with_update_alpine(self):
        """Test Dockerfile generation with default package update for Alpine."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'alpine:3.14'
        distro_info = {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
        packages = ['nmap']
        
        # Default behavior: update packages (no_update=False)
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False)
        
        # Check that apk update is included
        self.assertIn('apk update && apk add --no-cache nmap', dockerfile)

    def test_generate_dockerfile_without_update_alpine(self):
        """Test Dockerfile generation without package update for Alpine."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'alpine:3.14'
        distro_info = {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
        packages = ['nmap']
        
        # With --no-update flag (no_update=True)
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=True)
        
        # Check that apk update is NOT included in custom packages section
        self.assertNotIn('apk update && apk add --no-cache nmap', dockerfile)
        # But should have apk add without update
        self.assertIn('apk add --no-cache nmap', dockerfile)

    def test_generate_dockerfile_with_root_flag_alpine(self):
        """Test Dockerfile generation with --root flag for Alpine."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'alpine/nikto:latest'
        distro_info = {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
        packages = ['python3']
        
        # Test with run_as_root=True
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False, run_as_root=True)
        
        # Check that USER root directive is present
        self.assertIn('USER root', dockerfile)
        # Verify it comes after FROM
        from_idx = dockerfile.find('FROM')
        user_idx = dockerfile.find('USER root')
        self.assertLess(from_idx, user_idx)
        # And before RUN commands
        run_idx = dockerfile.find('RUN')
        self.assertLess(user_idx, run_idx)

    def test_generate_dockerfile_without_root_flag_alpine(self):
        """Test Dockerfile generation without --root flag for Alpine."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'alpine/nikto:latest'
        distro_info = {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
        packages = ['python3']
        
        # Test with run_as_root=False (default)
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False, run_as_root=False)
        
        # Check that USER root directive is NOT present
        self.assertNotIn('USER root', dockerfile)

    def test_generate_dockerfile_with_root_flag_debian(self):
        """Test Dockerfile generation with --root flag for Debian."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'ubuntu:20.04'
        distro_info = {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        packages = ['nmap']
        
        # Test with run_as_root=True
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False, run_as_root=True)
        
        # Check that USER root directive is present
        self.assertIn('USER root', dockerfile)
        # Verify proper ordering
        from_idx = dockerfile.find('FROM')
        user_idx = dockerfile.find('USER root')
        run_idx = dockerfile.find('RUN')
        self.assertLess(from_idx, user_idx)
        self.assertLess(user_idx, run_idx)

    def test_generate_dockerfile_with_root_flag_rhel(self):
        """Test Dockerfile generation with --root flag for RHEL."""
        # Create a minimal Acido object just to call the method
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        base_image = 'centos:7'
        distro_info = {'type': 'rhel', 'python_pkg': 'python3', 'pkg_manager': 'yum', 'needs_break_packages': False}
        packages = ['nmap']
        
        # Test with run_as_root=True
        dockerfile = acido._generate_dockerfile(base_image, distro_info, packages, no_update=False, run_as_root=True)
        
        # Check that USER root directive is present
        self.assertIn('USER root', dockerfile)
        # Verify proper ordering
        from_idx = dockerfile.find('FROM')
        user_idx = dockerfile.find('USER root')
        run_idx = dockerfile.find('RUN')
        self.assertLess(from_idx, user_idx)
        self.assertLess(user_idx, run_idx)


if __name__ == '__main__':
    unittest.main()

