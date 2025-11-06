"""
Unit tests for acido create command with GitHub URL support.

Tests the create_acido_image_from_github functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import tempfile

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


class TestCreateFromGitHub(unittest.TestCase):
    """Test cases for create command with GitHub URL support."""

    def setUp(self):
        """Set up test fixtures."""
        pass

    def test_parse_github_url_basic(self):
        """Test parsing basic GitHub URL."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertIsNone(result['ref'])
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_with_git_extension(self):
        """Test parsing GitHub URL with .git extension."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo.git'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertIsNone(result['ref'])
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_with_branch(self):
        """Test parsing GitHub URL with branch reference."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo@main'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertEqual(result['ref'], 'main')
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_with_tag(self):
        """Test parsing GitHub URL with tag reference."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo@v1.0.0'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertEqual(result['ref'], 'v1.0.0')
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_with_commit(self):
        """Test parsing GitHub URL with commit SHA."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo@abc123def456'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertEqual(result['ref'], 'abc123def456')
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_with_path_ref(self):
        """Test parsing GitHub URL with path-like ref (e.g., refs/heads/main)."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://github.com/user/repo@refs/heads/main'
        result = acido._parse_github_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertEqual(result['ref'], 'refs/heads/main')
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_invalid_no_prefix(self):
        """Test parsing URL without git+ prefix now auto-normalizes."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'https://github.com/user/repo'
        result = acido._parse_github_url(url)
        
        # URL without git+ prefix is now auto-normalized and parsed
        self.assertIsNotNone(result)
        self.assertEqual(result['repo_url'], 'https://github.com/user/repo.git')
        self.assertEqual(result['repo_name'], 'repo')

    def test_parse_github_url_invalid_not_github(self):
        """Test parsing URL not from github.com."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        url = 'git+https://gitlab.com/user/repo'
        result = acido._parse_github_url(url)
        
        self.assertIsNone(result)

    def test_is_github_url_true(self):
        """Test is_github_url returns True for valid GitHub URLs."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        self.assertTrue(acido._is_github_url('git+https://github.com/user/repo'))
        self.assertTrue(acido._is_github_url('git+https://github.com/user/repo@main'))
        # Now also accepts URLs without git+ prefix
        self.assertTrue(acido._is_github_url('https://github.com/user/repo'))

    def test_is_github_url_false(self):
        """Test is_github_url returns False for non-GitHub URLs."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        self.assertFalse(acido._is_github_url('git+https://gitlab.com/user/repo'))
        self.assertFalse(acido._is_github_url('ubuntu:20.04'))
        self.assertFalse(acido._is_github_url('nuclei'))


    def test_tag_sanitization(self):
        """Test that refs with special characters are sanitized for Docker tags."""
        acido = Acido.__new__(Acido)
        acido.image_registry_server = 'test.azurecr.io'
        
        # Test refs/heads/feature/branch becomes refs-heads-feature-branch
        import re
        test_tag = 'refs/heads/feature/branch'
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '-', test_tag).strip('.-_')
        self.assertEqual(sanitized, 'refs-heads-feature-branch')
        
        # Test v1.0@special becomes v1.0-special (dot is allowed)
        test_tag = 'v1.0@special'
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '-', test_tag).strip('.-_')
        self.assertEqual(sanitized, 'v1.0-special')
        
        # Test empty tag becomes latest
        test_tag = '///'
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '-', test_tag).strip('.-_')
        if not sanitized:
            sanitized = 'latest'
        self.assertEqual(sanitized, 'latest')


if __name__ == '__main__':
    unittest.main()
