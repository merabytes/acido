"""
Unit tests for AWS Lambda secrets handler.

Tests the lambda_handler_secrets function with various input scenarios.
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
    from lambda_handler_secrets import lambda_handler
finally:
    # Restore original argv
    sys.argv = _original_argv


class TestLambdaHandlerSecrets(unittest.TestCase):
    """Test cases for the Lambda secrets handler function."""

    def setUp(self):
        """Set up test fixtures."""
        # Set required environment variables for tests
        os.environ['KEY_VAULT_NAME'] = 'test-vault'
        os.environ['AZURE_TENANT_ID'] = 'test-tenant-id'
        os.environ['AZURE_CLIENT_ID'] = 'test-client-id'
        os.environ['AZURE_CLIENT_SECRET'] = 'test-secret'

    def test_missing_body(self):
        """Test handler with missing body."""
        event = {}
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing event body', body['error'])

    def test_missing_action(self):
        """Test handler with missing action."""
        event = {
            'secret': 'my-secret'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Invalid or missing action', body['error'])

    def test_invalid_action(self):
        """Test handler with invalid action."""
        event = {
            'action': 'invalid',
            'secret': 'my-secret'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Invalid or missing action', body['error'])

    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_secret_success(self, mock_uuid, mock_vault_manager_class):
        """Test successful secret creation."""
        # Setup mocks
        mock_uuid.return_value = 'test-uuid-1234'
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['uuid'], 'test-uuid-1234')
        self.assertIn('created successfully', body['message'])
        mock_vault_manager.set_secret.assert_called_once_with('test-uuid-1234', 'my-secret-value')

    @patch('lambda_handler_secrets.VaultManager')
    def test_create_secret_missing_secret(self, mock_vault_manager_class):
        """Test creating a secret without providing the secret value."""
        event = {
            'action': 'create'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required field: secret', body['error'])

    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_success(self, mock_vault_manager_class):
        """Test successful secret retrieval and deletion."""
        # Setup mocks
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        mock_vault_manager.get_secret.return_value = 'my-secret-value'
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['secret'], 'my-secret-value')
        self.assertIn('retrieved and deleted', body['message'])
        mock_vault_manager.secret_exists.assert_called_once_with('test-uuid-1234')
        mock_vault_manager.get_secret.assert_called_once_with('test-uuid-1234')
        mock_vault_manager.delete_secret.assert_called_once_with('test-uuid-1234')

    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_not_found(self, mock_vault_manager_class):
        """Test retrieving a secret that doesn't exist."""
        # Setup mocks
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = False
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Secret not found', body['error'])
        mock_vault_manager.secret_exists.assert_called_once_with('test-uuid-1234')
        mock_vault_manager.get_secret.assert_not_called()
        mock_vault_manager.delete_secret.assert_not_called()

    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_missing_uuid(self, mock_vault_manager_class):
        """Test retrieving a secret without providing UUID."""
        event = {
            'action': 'retrieve'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Missing required field: uuid', body['error'])

    @patch('lambda_handler_secrets.VaultManager')
    def test_body_wrapper(self, mock_vault_manager_class):
        """Test handler with body wrapper (from API Gateway)."""
        # Setup mocks
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'body': {
                'action': 'create',
                'secret': 'my-secret'
            }
        }
        context = {}
        
        with patch('lambda_handler_secrets.uuid.uuid4', return_value='test-uuid'):
            response = lambda_handler(event, context)
        
        # Should not return 400 (bad request)
        self.assertNotEqual(response['statusCode'], 400)

    @patch('lambda_handler_secrets.VaultManager')
    def test_string_event_parsing(self, mock_vault_manager_class):
        """Test handler with string event (should parse as JSON)."""
        # Setup mocks
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event_dict = {
            'action': 'create',
            'secret': 'my-secret'
        }
        event = json.dumps(event_dict)
        context = {}
        
        with patch('lambda_handler_secrets.uuid.uuid4', return_value='test-uuid'):
            response = lambda_handler(event, context)
        
        # Should parse successfully and not return 400
        self.assertNotEqual(response['statusCode'], 400)

    @patch('lambda_handler_secrets.VaultManager')
    def test_exception_handling(self, mock_vault_manager_class):
        """Test exception handling in Lambda."""
        # Make VaultManager raise an exception
        mock_vault_manager_class.side_effect = Exception('Test error')
        
        event = {
            'action': 'create',
            'secret': 'my-secret'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 500 error
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Test error', body['error'])


if __name__ == '__main__':
    unittest.main()
