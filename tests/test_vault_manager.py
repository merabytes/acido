"""
Unit tests for VaultManager extensions.

Tests the new set_secret, delete_secret, and secret_exists methods.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from azure.core.exceptions import ResourceNotFoundError
import os
import sys

# Mock sys.argv to prevent argparse from processing test args
_original_argv = sys.argv
sys.argv = ['test']

try:
    from acido.azure_utils.VaultManager import VaultManager
finally:
    # Restore original argv
    sys.argv = _original_argv


class TestVaultManagerExtensions(unittest.TestCase):
    """Test cases for VaultManager secret management methods."""

    def setUp(self):
        """Set up test fixtures."""
        os.environ['KEY_VAULT_NAME'] = 'test-vault'
        os.environ['AZURE_TENANT_ID'] = 'test-tenant-id'
        os.environ['AZURE_CLIENT_ID'] = 'test-client-id'
        os.environ['AZURE_CLIENT_SECRET'] = 'test-secret'

    @patch('acido.azure_utils.VaultManager.SecretClient')
    @patch('acido.azure_utils.VaultManager.ManagedIdentity.get_credential')
    def test_set_secret(self, mock_get_credential, mock_secret_client_class):
        """Test setting a secret in Key Vault."""
        # Setup mocks
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential
        
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = 'test-value'
        mock_client.set_secret.return_value = mock_secret
        
        # Create VaultManager and set secret
        vault_manager = VaultManager()
        result = vault_manager.set_secret('test-key', 'test-value')
        
        # Verify
        mock_client.set_secret.assert_called_once_with('test-key', 'test-value')
        self.assertEqual(result.value, 'test-value')

    @patch('acido.azure_utils.VaultManager.SecretClient')
    @patch('acido.azure_utils.VaultManager.ManagedIdentity.get_credential')
    def test_delete_secret(self, mock_get_credential, mock_secret_client_class):
        """Test deleting a secret from Key Vault."""
        # Setup mocks
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential
        
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client
        
        mock_poller = Mock()
        mock_deleted_secret = Mock()
        mock_poller.result.return_value = mock_deleted_secret
        mock_client.begin_delete_secret.return_value = mock_poller
        
        # Create VaultManager and delete secret
        vault_manager = VaultManager()
        result = vault_manager.delete_secret('test-key')
        
        # Verify
        mock_client.begin_delete_secret.assert_called_once_with('test-key')
        mock_poller.result.assert_called_once()

    @patch('acido.azure_utils.VaultManager.SecretClient')
    @patch('acido.azure_utils.VaultManager.ManagedIdentity.get_credential')
    def test_secret_exists_true(self, mock_get_credential, mock_secret_client_class):
        """Test checking if a secret exists (exists case)."""
        # Setup mocks
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential
        
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = 'test-value'
        mock_client.get_secret.return_value = mock_secret
        
        # Create VaultManager and check existence
        vault_manager = VaultManager()
        result = vault_manager.secret_exists('test-key')
        
        # Verify
        self.assertTrue(result)
        mock_client.get_secret.assert_called_once_with('test-key')

    @patch('acido.azure_utils.VaultManager.SecretClient')
    @patch('acido.azure_utils.VaultManager.ManagedIdentity.get_credential')
    def test_secret_exists_false(self, mock_get_credential, mock_secret_client_class):
        """Test checking if a secret exists (does not exist case)."""
        # Setup mocks
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential
        
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client
        
        mock_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        # Create VaultManager and check existence
        vault_manager = VaultManager()
        result = vault_manager.secret_exists('test-key')
        
        # Verify
        self.assertFalse(result)
        mock_client.get_secret.assert_called_once_with('test-key')

    @patch('acido.azure_utils.VaultManager.SecretClient')
    @patch('acido.azure_utils.VaultManager.ManagedIdentity.get_credential')
    def test_get_secret_existing(self, mock_get_credential, mock_secret_client_class):
        """Test getting an existing secret (original method still works)."""
        # Setup mocks
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential
        
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = 'test-value'
        mock_client.get_secret.return_value = mock_secret
        
        # Create VaultManager and get secret
        vault_manager = VaultManager()
        result = vault_manager.get_secret('test-key')
        
        # Verify
        self.assertEqual(result, 'test-value')
        mock_client.get_secret.assert_called_once_with('test-key')


if __name__ == '__main__':
    unittest.main()
