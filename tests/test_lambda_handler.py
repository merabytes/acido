"""
Unit tests for AWS Lambda handler.

Tests the lambda_handler function with various input scenarios.
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


class TestLambdaHandler(unittest.TestCase):
    """Test cases for the Lambda handler function."""

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

    def test_missing_body(self):
        """Test handler with missing body."""
        event = {}
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing event body', body['error'])

    def test_missing_required_fields(self):
        """Test handler with missing required fields."""
        event = {
            'body': {
                'image': 'nmap'
                # Missing targets and task
            }
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required fields', body['error'])

    def test_invalid_targets(self):
        """Test handler with invalid targets."""
        event = {
            'body': {
                'image': 'nmap',
                'targets': [],  # Empty list
                'task': 'nmap -iL input'
            }
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('non-empty list', body['error'])

    def test_string_event_parsing(self):
        """Test handler with string event (should parse as JSON)."""
        event_dict = {
            'image': 'nmap',
            'targets': ['example.com'],
            'task': 'nmap -iL input'
        }
        event = json.dumps(event_dict)
        context = {}
        
        # Mock Acido to avoid actual Azure calls
        with patch('lambda_handler.Acido') as mock_acido_class:
            mock_acido = MagicMock()
            mock_acido_class.return_value = mock_acido
            mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
            mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
            
            with patch('lambda_handler.ThreadPoolShim'):
                response = lambda_handler(event, context)
        
        # Should parse successfully and not return 400
        self.assertNotEqual(response['statusCode'], 400)

    def test_body_wrapper(self):
        """Test handler with body wrapper."""
        event = {
            'body': {
                'image': 'nmap',
                'targets': ['example.com'],
                'task': 'nmap -iL input'
            }
        }
        context = {}
        
        # Mock Acido to avoid actual Azure calls
        with patch('lambda_handler.Acido') as mock_acido_class:
            mock_acido = MagicMock()
            mock_acido_class.return_value = mock_acido
            mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
            mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
            
            with patch('lambda_handler.ThreadPoolShim'):
                response = lambda_handler(event, context)
        
        # Should not return 400 (bad request)
        self.assertNotEqual(response['statusCode'], 400)

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_successful_execution(self, mock_acido_class, mock_pool, mock_temp_file):
        """Test successful Lambda execution."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = (
            {'lambda-fleet': ['container-1']},
            {'container-1': 'scan results here'}
        )
        
        # Test event
        event = {
            'image': 'nmap',
            'targets': ['merabytes.com', 'uber.com'],
            'task': 'nmap -iL input -p 0-1000'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify response
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['fleet_name'], 'lambda-fleet')
        self.assertEqual(body['instances'], 2)
        self.assertEqual(body['image'], 'nmap')
        self.assertIn('outputs', body)

    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_exception_handling(self, mock_acido_class, mock_pool):
        """Test exception handling in Lambda."""
        # Make Acido raise an exception
        mock_acido_class.side_effect = Exception('Test error')
        
        event = {
            'image': 'nmap',
            'targets': ['example.com'],
            'task': 'nmap -iL input'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 500 error
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Test error', body['error'])

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('lambda_handler.Acido')
    def test_custom_fleet_name(self, mock_acido_class, mock_pool, mock_temp_file):
        """Test with custom fleet name."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = (
            {'custom-fleet': ['container-1']},
            {'container-1': 'results'}
        )
        
        event = {
            'image': 'nmap',
            'targets': ['example.com'],
            'task': 'nmap -iL input',
            'fleet_name': 'custom-fleet'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['fleet_name'], 'custom-fleet')

    @patch('lambda_handler.Acido')
    def test_ls_operation(self, mock_acido_class):
        """Test ls operation to list container instances."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.ls.return_value = (
            {'fleet-1': ['container-1', 'container-2']},
            {'fleet-1': ['container-1', 'container-2']}
        )
        
        event = {
            'operation': 'ls'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'ls')
        self.assertIn('instances', body)
        self.assertEqual(len(body['instances']), 1)
        self.assertEqual(body['instances'][0]['container_group'], 'fleet-1')

    @patch('lambda_handler.Acido')
    def test_rm_operation(self, mock_acido_class):
        """Test rm operation to remove container instances."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.rm.return_value = None
        
        event = {
            'operation': 'rm',
            'name': 'fleet-1'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'rm')
        self.assertIn('result', body)
        self.assertEqual(body['result']['removed'], 'fleet-1')
        
        # Verify rm was called with correct name
        mock_acido.rm.assert_called_once_with('fleet-1')

    def test_rm_missing_name(self):
        """Test rm operation with missing name field."""
        event = {
            'operation': 'rm'
            # Missing name field
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required fields', body['error'])

    @patch('lambda_handler.Acido')
    def test_ip_create_operation(self, mock_acido_class):
        """Test ip_create operation to create IPv4 address."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.create_ipv4_address.return_value = None
        
        event = {
            'operation': 'ip_create',
            'name': 'pentest-ip'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'ip_create')
        self.assertIn('result', body)
        self.assertEqual(body['result']['created'], 'pentest-ip')
        
        # Verify create_ipv4_address was called with correct name
        mock_acido.create_ipv4_address.assert_called_once_with('pentest-ip')

    @patch('lambda_handler.Acido')
    def test_ip_ls_operation(self, mock_acido_class):
        """Test ip_ls operation to list IPv4 addresses."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.ls_ip.return_value = [
            {'name': 'pentest-ip', 'ip_address': '20.123.45.67'}
        ]
        
        event = {
            'operation': 'ip_ls'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'ip_ls')
        self.assertIn('ip_addresses', body)
        self.assertEqual(len(body['ip_addresses']), 1)
        self.assertEqual(body['ip_addresses'][0]['name'], 'pentest-ip')

    @patch('lambda_handler.Acido')
    def test_ip_rm_operation(self, mock_acido_class):
        """Test ip_rm operation to remove IPv4 address."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.rm_ip.return_value = True
        
        event = {
            'operation': 'ip_rm',
            'name': 'pentest-ip'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'ip_rm')
        self.assertIn('result', body)
        self.assertEqual(body['result']['removed'], 'pentest-ip')
        self.assertTrue(body['result']['success'])
        
        # Verify rm_ip was called with correct name
        mock_acido.rm_ip.assert_called_once_with('pentest-ip')

    def test_ip_create_missing_name(self):
        """Test ip_create operation with missing name field."""
        event = {
            'operation': 'ip_create'
            # Missing name field
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required fields', body['error'])

    def test_ip_rm_missing_name(self):
        """Test ip_rm operation with missing name field."""
        event = {
            'operation': 'ip_rm'
            # Missing name field
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required fields', body['error'])


if __name__ == '__main__':
    unittest.main()
