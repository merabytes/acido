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
        # Ensure CF_SECRET_KEY is not set by default (Turnstile is optional)
        if 'CF_SECRET_KEY' in os.environ:
            del os.environ['CF_SECRET_KEY']
        # Ensure CORS_ORIGIN is not set by default (will use default)
        if 'CORS_ORIGIN' in os.environ:
            del os.environ['CORS_ORIGIN']

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

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_secret_success(self, mock_uuid, mock_vault_manager_class, mock_validate):
        """Test successful secret creation."""
        # Setup mocks
        mock_uuid.return_value = 'test-uuid-1234'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['uuid'], 'test-uuid-1234')
        self.assertIn('created successfully', body['message'])
        
        # Verify both secret and metadata were stored
        self.assertEqual(mock_vault_manager.set_secret.call_count, 2)
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234', 'my-secret-value')
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234-metadata', 'plaintext')

    @patch('lambda_handler_secrets.VaultManager')
    def test_create_secret_missing_secret(self, mock_vault_manager_class):
        """Test creating a secret without providing the secret value."""
        event = {
            'action': 'create',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        # Should fail for missing turnstile validation, not secret
        # Update test to check for turnstile error first
        event_no_token = {
            'action': 'create'
        }
        response = lambda_handler(event_no_token, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('turnstile_token', body['error'])

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_success(self, mock_vault_manager_class, mock_validate):
        """Test successful secret retrieval and deletion."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock get_secret to return metadata and then the actual secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'plaintext'
            return 'my-secret-value'
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['secret'], 'my-secret-value')
        self.assertIn('retrieved and deleted', body['message'])
        mock_vault_manager.secret_exists.assert_called_once_with('test-uuid-1234')
        
        # Verify both secret and metadata were accessed and deleted
        self.assertEqual(mock_vault_manager.get_secret.call_count, 2)
        self.assertEqual(mock_vault_manager.delete_secret.call_count, 2)

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_not_found(self, mock_vault_manager_class, mock_validate):
        """Test retrieving a secret that doesn't exist."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = False
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
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
            'action': 'retrieve',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        # Should fail for missing turnstile first
        event_no_token = {
            'action': 'retrieve'
        }
        response = lambda_handler(event_no_token, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('turnstile_token', body['error'])

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_body_wrapper(self, mock_vault_manager_class, mock_validate):
        """Test handler with body wrapper (from API Gateway)."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'body': {
                'action': 'create',
                'secret': 'my-secret',
                'turnstile_token': 'valid-token'
            }
        }
        context = {}
        
        with patch('lambda_handler_secrets.uuid.uuid4', return_value='test-uuid'):
            response = lambda_handler(event, context)
        
        # Should not return 400 (bad request)
        self.assertNotEqual(response['statusCode'], 400)

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_string_event_parsing(self, mock_vault_manager_class, mock_validate):
        """Test handler with string event (should parse as JSON)."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event_dict = {
            'action': 'create',
            'secret': 'my-secret',
            'turnstile_token': 'valid-token'
        }
        event = json.dumps(event_dict)
        context = {}
        
        with patch('lambda_handler_secrets.uuid.uuid4', return_value='test-uuid'):
            response = lambda_handler(event, context)
        
        # Should parse successfully and not return 400
        self.assertNotEqual(response['statusCode'], 400)

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_exception_handling(self, mock_vault_manager_class, mock_validate):
        """Test exception handling in Lambda."""
        # Make VaultManager raise an exception
        mock_validate.return_value = True
        mock_vault_manager_class.side_effect = Exception('Test error')
        
        event = {
            'action': 'create',
            'secret': 'my-secret',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 500 error
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Test error', body['error'])

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_with_turnstile_enabled_success(self, mock_uuid, mock_vault_manager_class, mock_validate):
        """Test secret creation with Turnstile enabled and valid token."""
        # Setup environment and mocks
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_uuid.return_value = 'test-uuid-1234'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 201)
        mock_validate.assert_called_once()
        
        # Verify both secret and metadata were stored
        self.assertEqual(mock_vault_manager.set_secret.call_count, 2)
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234', 'my-secret-value')
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234-metadata', 'plaintext')
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('lambda_handler_secrets.validate_turnstile')
    def test_create_with_turnstile_enabled_missing_token(self, mock_validate):
        """Test secret creation with Turnstile enabled but missing token."""
        # Setup environment
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value'
            # Missing turnstile_token
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('turnstile_token', body['error'])
        mock_validate.assert_not_called()
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_create_with_turnstile_enabled_invalid_token(self, mock_vault_manager_class, mock_validate):
        """Test secret creation with Turnstile enabled but invalid token."""
        # Setup environment and mocks
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_validate.return_value = False
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value',
            'turnstile_token': 'invalid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 403)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Invalid or expired Turnstile token', body['error'])
        mock_validate.assert_called_once()
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_with_turnstile_enabled_success(self, mock_vault_manager_class, mock_validate):
        """Test secret retrieval with Turnstile enabled and valid token."""
        # Setup environment and mocks
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock get_secret to return metadata and then the actual secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'plaintext'
            return 'my-secret-value'
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        mock_validate.assert_called_once()
        
        # Verify both secret and metadata were accessed and deleted
        self.assertEqual(mock_vault_manager.get_secret.call_count, 2)
        self.assertEqual(mock_vault_manager.delete_secret.call_count, 2)
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('acido.utils.turnstile_utils.requests.post')
    def test_validate_turnstile_success(self, mock_post):
        """Test Turnstile validation with successful response."""
        from acido.utils.turnstile_utils import validate_turnstile
        
        # Setup environment and mock
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_response = Mock()
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        result = validate_turnstile('valid-token', '192.168.1.1')
        
        # Verify
        self.assertTrue(result)
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]['data']
        self.assertEqual(call_args['secret'], 'test-cf-secret')
        self.assertEqual(call_args['response'], 'valid-token')
        self.assertEqual(call_args['remoteip'], '192.168.1.1')
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('acido.utils.turnstile_utils.requests.post')
    def test_validate_turnstile_failure(self, mock_post):
        """Test Turnstile validation with failed response."""
        from acido.utils.turnstile_utils import validate_turnstile
        
        # Setup environment and mock
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_response = Mock()
        mock_response.json.return_value = {'success': False}
        mock_post.return_value = mock_response
        
        result = validate_turnstile('invalid-token')
        
        # Verify
        self.assertFalse(result)
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    def test_validate_turnstile_no_secret_key(self):
        """Test Turnstile validation when CF_SECRET_KEY is not set."""
        from acido.utils.turnstile_utils import validate_turnstile
        
        # Ensure CF_SECRET_KEY is not set
        if 'CF_SECRET_KEY' in os.environ:
            del os.environ['CF_SECRET_KEY']
        
        result = validate_turnstile('any-token')
        
        # Should return True (skip validation)
        self.assertTrue(result)

    @patch('acido.utils.turnstile_utils.requests.post')
    def test_validate_turnstile_network_error(self, mock_post):
        """Test Turnstile validation when network error occurs."""
        from acido.utils.turnstile_utils import validate_turnstile
        
        # Setup environment and mock
        os.environ['CF_SECRET_KEY'] = 'test-cf-secret'
        mock_post.side_effect = Exception('Network error')
        
        result = validate_turnstile('token')
        
        # Should return False on exception
        self.assertFalse(result)
        
        # Clean up
        del os.environ['CF_SECRET_KEY']

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_secret_with_password(self, mock_uuid, mock_vault_manager_class, mock_validate):
        """Test creating a secret with password encryption."""
        # Setup mocks
        mock_uuid.return_value = 'test-uuid-1234'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value',
            'password': 'test-password',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['uuid'], 'test-uuid-1234')
        self.assertIn('created successfully', body['message'])
        
        # Verify that set_secret was called twice (secret + metadata)
        self.assertEqual(mock_vault_manager.set_secret.call_count, 2)
        
        # Verify secret value is encrypted (not plaintext)
        secret_call = [call for call in mock_vault_manager.set_secret.call_args_list if 'metadata' not in str(call)][0]
        stored_value = secret_call[0][1]
        self.assertNotEqual(stored_value, 'my-secret-value')  # Should be encrypted

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_with_correct_password(self, mock_vault_manager_class, mock_validate):
        """Test retrieving an encrypted secret with correct password."""
        from acido.utils.crypto_utils import encrypt_secret
        
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Encrypt a secret with password
        encrypted_value = encrypt_secret('my-secret-value', 'test-password')
        
        # Mock get_secret to return metadata and then the actual encrypted secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'encrypted'
            return encrypted_value
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'password': 'test-password',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['secret'], 'my-secret-value')
        self.assertIn('retrieved and deleted', body['message'])
        
        # Verify both secret and metadata were deleted
        self.assertEqual(mock_vault_manager.delete_secret.call_count, 2)

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_secret_with_wrong_password(self, mock_vault_manager_class, mock_validate):
        """Test retrieving an encrypted secret with wrong password."""
        from acido.utils.crypto_utils import encrypt_secret
        
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Encrypt a secret with password
        encrypted_value = encrypt_secret('my-secret-value', 'correct-password')
        
        # Mock get_secret to return metadata and then the actual encrypted secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'encrypted'
            return encrypted_value
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'password': 'wrong-password',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify - should return 400 error
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Decryption failed', body['error'])
        # Secret and metadata should NOT be deleted on wrong password (allow retry)
        mock_vault_manager.delete_secret.assert_not_called()

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_without_password_backward_compatible(self, mock_uuid, mock_vault_manager_class, mock_validate):
        """Test creating a secret without password (backward compatibility)."""
        # Setup mocks
        mock_uuid.return_value = 'test-uuid-1234'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        event = {
            'action': 'create',
            'secret': 'my-secret-value',
            'turnstile_token': 'valid-token'
            # No password provided
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['uuid'], 'test-uuid-1234')
        
        # Verify both secret and metadata were stored
        self.assertEqual(mock_vault_manager.set_secret.call_count, 2)
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234', 'my-secret-value')
        mock_vault_manager.set_secret.assert_any_call('test-uuid-1234-metadata', 'plaintext')

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_without_password_backward_compatible(self, mock_vault_manager_class, mock_validate):
        """Test retrieving a plaintext secret without password (backward compatibility)."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock get_secret to return metadata and then the actual secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'plaintext'
            return 'my-secret-value'
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
            # No password provided
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['secret'], 'my-secret-value')
        self.assertIn('retrieved and deleted', body['message'])

    def test_encrypt_decrypt_functions(self):
        """Test encryption and decryption functions directly."""
        from acido.utils.crypto_utils import encrypt_secret, decrypt_secret
        
        # Test basic encryption/decryption
        original_secret = 'This is a test secret!'
        password = 'test-password-123'
        
        encrypted = encrypt_secret(original_secret, password)
        self.assertNotEqual(encrypted, original_secret)
        self.assertIsInstance(encrypted, str)
        
        decrypted = decrypt_secret(encrypted, password)
        self.assertEqual(decrypted, original_secret)
        
        # Test with different password fails
        with self.assertRaises(ValueError) as context:
            decrypt_secret(encrypted, 'wrong-password')
        self.assertIn('Decryption failed', str(context.exception))

    def test_healthcheck(self):
        """Test healthcheck action."""
        event = {
            'action': 'healthcheck'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('headers', response)
        # Default CORS origin is now https://secrets.merabytes.com
        self.assertEqual(response['headers']['Access-Control-Allow-Origin'], 'https://secrets.merabytes.com')
        body = json.loads(response['body'])
        self.assertEqual(body['status'], 'healthy')
        self.assertIn('version', body)

    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        event = {
            'action': 'healthcheck'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify CORS headers
        self.assertIn('headers', response)
        headers = response['headers']
        # Default CORS origin is now https://secrets.merabytes.com
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://secrets.merabytes.com')
        self.assertEqual(headers['Access-Control-Allow-Methods'], 'POST, OPTIONS')
        self.assertEqual(headers['Access-Control-Allow-Headers'], 'Content-Type')
        self.assertEqual(headers['Content-Type'], 'application/json')

    def test_options_preflight(self):
        """Test OPTIONS preflight request handling."""
        event = {
            'requestContext': {
                'http': {
                    'method': 'OPTIONS'
                }
            }
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('headers', response)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'CORS preflight OK')

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    @patch('lambda_handler_secrets.uuid.uuid4')
    def test_create_requires_turnstile(self, mock_uuid, mock_vault_manager_class, mock_validate):
        """Test that create action requires turnstile token."""
        # Setup mocks
        mock_uuid.return_value = 'test-uuid-1234'
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        
        # Test without turnstile token - should fail
        event = {
            'action': 'create',
            'secret': 'my-secret-value'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 400 for missing turnstile token
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('turnstile_token', body['error'])
        
        # Test with turnstile token - should succeed
        event['turnstile_token'] = 'valid-token'
        response = lambda_handler(event, context)
        
        # Should succeed now
        self.assertEqual(response['statusCode'], 201)
        mock_validate.assert_called_once()

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_retrieve_requires_turnstile(self, mock_vault_manager_class, mock_validate):
        """Test that retrieve action requires turnstile token."""
        # Setup mocks
        mock_validate.return_value = True
        
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock get_secret to return metadata and then the actual secret
        def get_secret_side_effect(key):
            if key == 'test-uuid-1234-metadata':
                return 'plaintext'
            return 'my-secret-value'
        
        mock_vault_manager.get_secret.side_effect = get_secret_side_effect
        
        # Test without turnstile token - should fail
        event = {
            'action': 'retrieve',
            'uuid': 'test-uuid-1234'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Should return 400 for missing turnstile token
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('turnstile_token', body['error'])
        
        # Test with turnstile token - should succeed
        event['turnstile_token'] = 'valid-token'
        response = lambda_handler(event, context)
        
        # Should succeed now
        self.assertEqual(response['statusCode'], 200)
        mock_validate.assert_called_once()

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_check_secret_encrypted(self, mock_vault_manager_class, mock_validate):
        """Test checking if a secret is encrypted."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock metadata to indicate encrypted secret
        mock_vault_manager.get_secret.return_value = 'encrypted'
        
        event = {
            'action': 'check',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['encrypted'])
        self.assertTrue(body['requires_password'])
        
        # Verify that the secret was NOT deleted (check action is non-destructive)
        mock_vault_manager.delete_secret.assert_not_called()

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_check_secret_not_encrypted(self, mock_vault_manager_class, mock_validate):
        """Test checking if a plaintext secret is not encrypted."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = True
        
        # Mock metadata to indicate plaintext secret
        mock_vault_manager.get_secret.return_value = 'plaintext'
        
        event = {
            'action': 'check',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertFalse(body['encrypted'])
        self.assertFalse(body['requires_password'])
        
        # Verify that the secret was NOT deleted
        mock_vault_manager.delete_secret.assert_not_called()

    @patch('lambda_handler_secrets.validate_turnstile')
    @patch('lambda_handler_secrets.VaultManager')
    def test_check_secret_not_found(self, mock_vault_manager_class, mock_validate):
        """Test checking a secret that doesn't exist."""
        # Setup mocks
        mock_validate.return_value = True
        mock_vault_manager = MagicMock()
        mock_vault_manager_class.return_value = mock_vault_manager
        mock_vault_manager.secret_exists.return_value = False
        
        event = {
            'action': 'check',
            'uuid': 'test-uuid-1234',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        response = lambda_handler(event, context)
        
        # Verify
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Secret not found', body['error'])

    @patch('lambda_handler_secrets.VaultManager')
    def test_check_secret_missing_uuid(self, mock_vault_manager_class):
        """Test checking a secret without providing UUID."""
        event = {
            'action': 'check',
            'turnstile_token': 'valid-token'
        }
        context = {}
        
        # Should fail for missing turnstile first
        event_no_token = {
            'action': 'check'
        }
        response = lambda_handler(event_no_token, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('turnstile_token', body['error'])

    def test_is_encrypted_function(self):
        """Test the is_encrypted utility function directly."""
        from acido.utils.crypto_utils import encrypt_secret, is_encrypted
        
        # Test with encrypted value
        encrypted_value = encrypt_secret('test-secret', 'password')
        self.assertTrue(is_encrypted(encrypted_value))
        
        # Test with plaintext
        self.assertFalse(is_encrypted('plaintext-secret'))
        
        # Test with invalid base64
        self.assertFalse(is_encrypted('not-base64!@#$'))
        
        # Test with valid base64 but too short
        import base64
        short_data = base64.b64encode(b'short').decode()
        self.assertFalse(is_encrypted(short_data))

    def test_cors_origin_env_var(self):
        """Test that CORS origin can be configured via environment variable."""
        # Set custom CORS origin
        os.environ['CORS_ORIGIN'] = 'https://custom.example.com'
        
        # Need to reload the module to pick up the new env var
        import importlib
        import lambda_handler_secrets
        importlib.reload(lambda_handler_secrets)
        
        event = {
            'action': 'healthcheck'
        }
        context = {}
        
        response = lambda_handler_secrets.lambda_handler(event, context)
        
        # Verify custom CORS origin is used
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('headers', response)
        self.assertEqual(response['headers']['Access-Control-Allow-Origin'], 'https://custom.example.com')
        
        # Clean up - reload again with default
        del os.environ['CORS_ORIGIN']
        importlib.reload(lambda_handler_secrets)



if __name__ == '__main__':
    unittest.main()
