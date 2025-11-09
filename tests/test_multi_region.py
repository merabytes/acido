"""
Unit tests for multi-region support in acido.
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Mock sys.argv to prevent argparse from processing test args
_original_argv = sys.argv
sys.argv = ['test']

try:
    from lambda_handler import lambda_handler
finally:
    # Restore original argv
    sys.argv = _original_argv


class TestMultiRegionSupport(unittest.TestCase):
    """Test cases for multi-region support."""

    def setUp(self):
        """Set up test fixtures."""
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

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_fleet_with_regions_list(self, mock_acido_class, mock_pool, mock_temp_file):
        """Test fleet operation with multiple regions as list."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
        
        event = {
            'operation': 'fleet',
            'image': 'nmap',
            'targets': ['example.com', 'test.com'],
            'task': 'nmap -iL input',
            'regions': ['westeurope', 'eastus', 'westus2']
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify success
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'fleet')
        self.assertEqual(body['regions'], ['westeurope', 'eastus', 'westus2'])
        
        # Verify fleet was called with regions list
        mock_acido.fleet.assert_called_once()
        call_kwargs = mock_acido.fleet.call_args[1]
        self.assertEqual(call_kwargs['regions'], ['westeurope', 'eastus', 'westus2'])

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_fleet_with_single_region_string(self, mock_acido_class, mock_pool, mock_temp_file):
        """Test fleet operation with single region as string (backward compatibility)."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
        
        event = {
            'operation': 'fleet',
            'image': 'nmap',
            'targets': ['example.com'],
            'task': 'nmap -iL input',
            'region': 'westeurope'  # Single region as string
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify success
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'fleet')
        # Should be converted to list
        self.assertEqual(body['regions'], ['westeurope'])
        
        # Verify fleet was called with regions as list
        mock_acido.fleet.assert_called_once()
        call_kwargs = mock_acido.fleet.call_args[1]
        self.assertEqual(call_kwargs['regions'], ['westeurope'])

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_fleet_without_region_defaults_to_westeurope(self, mock_acido_class, mock_pool, mock_temp_file):
        """Test fleet operation without region parameter defaults to westeurope."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
        
        event = {
            'operation': 'fleet',
            'image': 'nmap',
            'targets': ['example.com'],
            'task': 'nmap -iL input'
            # No region/regions parameter
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify success
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'fleet')
        # Should default to ['westeurope']
        self.assertEqual(body['regions'], ['westeurope'])
        
        # Verify fleet was called with default region
        mock_acido.fleet.assert_called_once()
        call_kwargs = mock_acido.fleet.call_args[1]
        self.assertEqual(call_kwargs['regions'], ['westeurope'])

    @patch('lambda_handler.Acido')
    def test_run_with_regions_list(self, mock_acido_class):
        """Test run operation with multiple regions."""
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/runner-acido:latest'
        mock_acido.run.return_value = ({}, {'container-1': 'output'})
        
        event = {
            'operation': 'run',
            'name': 'test-runner',
            'image': 'runner',
            'task': './run.sh',
            'regions': ['westeurope', 'eastus']
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify success
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'run')
        self.assertEqual(body['regions'], ['westeurope', 'eastus'])
        
        # Verify run was called with regions list
        mock_acido.run.assert_called_once()
        call_kwargs = mock_acido.run.call_args[1]
        self.assertEqual(call_kwargs['regions'], ['westeurope', 'eastus'])


if __name__ == '__main__':
    unittest.main()
