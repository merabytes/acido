"""
Unit tests for AWS Lambda handler run operation.

Tests the lambda_handler function with run operation for ephemeral instances.
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


class TestLambdaHandlerRun(unittest.TestCase):
    """Test cases for the Lambda handler run operation."""

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

    def test_run_operation_missing_required_fields(self):
        """Test run operation with missing required fields."""
        event = {
            'operation': 'run',
            'name': 'test-runner'
            # Missing image and task
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required fields', body['error'])

    def test_run_operation_invalid_operation(self):
        """Test with invalid operation type."""
        event = {
            'operation': 'invalid',
            'name': 'test-runner',
            'image': 'test-image',
            'task': './run.sh'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Invalid operation', body['error'])

    @patch('lambda_handler.Acido')
    def test_run_operation_successful_execution(self, mock_acido_class):
        """Test successful run operation execution."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/github-runner-acido:latest'
        mock_acido.run.return_value = (
            {'test-runner-01': True},
            {'test-runner-01-01': 'runner output'}
        )
        
        # Test event
        event = {
            'operation': 'run',
            'name': 'test-runner-01',
            'image': 'github-runner',
            'task': './run.sh --url https://github.com/test/repo',
            'duration': 600,
            'cleanup': True
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify response
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['operation'], 'run')
        self.assertEqual(body['name'], 'test-runner-01')
        self.assertEqual(body['image'], 'github-runner')
        self.assertEqual(body['duration'], 600)
        self.assertEqual(body['cleanup'], True)
        self.assertIn('outputs', body)
        
        # Verify run was called with correct parameters
        mock_acido.run.assert_called_once()

    @patch('lambda_handler.Acido')
    def test_run_operation_default_duration(self, mock_acido_class):
        """Test run operation with default duration."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/github-runner-acido:latest'
        mock_acido.run.return_value = ({}, {})
        
        event = {
            'operation': 'run',
            'name': 'test-runner',
            'image': 'github-runner',
            'task': './run.sh'
            # No duration specified
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['duration'], 900)  # Default 15 minutes

    @patch('lambda_handler.Acido')
    def test_run_operation_default_cleanup(self, mock_acido_class):
        """Test run operation with default cleanup."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/github-runner-acido:latest'
        mock_acido.run.return_value = ({}, {})
        
        event = {
            'operation': 'run',
            'name': 'test-runner',
            'image': 'github-runner',
            'task': './run.sh'
            # No cleanup specified
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['cleanup'], True)  # Default to True

    @patch('lambda_handler.Acido')
    def test_run_operation_no_cleanup(self, mock_acido_class):
        """Test run operation with cleanup disabled."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/github-runner-acido:latest'
        mock_acido.run.return_value = ({}, {})
        
        event = {
            'operation': 'run',
            'name': 'test-runner',
            'image': 'github-runner',
            'task': './run.sh',
            'cleanup': False
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['cleanup'], False)

    @patch('lambda_handler.Acido')
    def test_run_operation_exception_handling(self, mock_acido_class):
        """Test exception handling in run operation."""
        # Make Acido.run raise an exception
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/github-runner-acido:latest'
        mock_acido.run.side_effect = Exception('Test error')
        
        event = {
            'operation': 'run',
            'name': 'test-runner',
            'image': 'github-runner',
            'task': './run.sh'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 500 error
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Test error', body['error'])

    @patch('lambda_handler.Acido')
    def test_backward_compatibility_fleet_operation(self, mock_acido_class):
        """Test that fleet operation still works (backward compatibility)."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp_file:
            mock_file = MagicMock()
            mock_file.name = '/tmp/test-input.txt'
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_temp_file.return_value = mock_file
            
            with patch('lambda_handler.ThreadPoolShim'):
                # Test with explicit fleet operation
                event = {
                    'operation': 'fleet',
                    'image': 'nmap',
                    'targets': ['example.com'],
                    'task': 'nmap -iL input'
                }
                context = {}
                
                response = lambda_handler(event, context)
                
                self.assertEqual(response['statusCode'], 200)
                body = json.loads(response['body'])
                self.assertEqual(body['operation'], 'fleet')

    @patch('lambda_handler.Acido')
    def test_default_operation_is_fleet(self, mock_acido_class):
        """Test that default operation is fleet for backward compatibility."""
        # Setup mocks
        mock_acido = MagicMock()
        mock_acido_class.return_value = mock_acido
        mock_acido.build_image_url.return_value = 'test.azurecr.io/nmap-acido:latest'
        mock_acido.fleet.return_value = ({}, {'container-1': 'output'})
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp_file:
            mock_file = MagicMock()
            mock_file.name = '/tmp/test-input.txt'
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_temp_file.return_value = mock_file
            
            with patch('lambda_handler.ThreadPoolShim'):
                # Test without operation field (should default to fleet)
                event = {
                    'image': 'nmap',
                    'targets': ['example.com'],
                    'task': 'nmap -iL input'
                }
                context = {}
                
                response = lambda_handler(event, context)
                
                self.assertEqual(response['statusCode'], 200)
                body = json.loads(response['body'])
                self.assertEqual(body['operation'], 'fleet')


if __name__ == '__main__':
    unittest.main()
