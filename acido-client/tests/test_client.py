"""
Unit tests for acido-client.

Tests the AcidoClient class and CLI functionality.
"""

import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from acido_client import AcidoClient, AcidoClientError


class TestAcidoClient(unittest.TestCase):
    """Test cases for AcidoClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.lambda_url = "https://test.lambda-url.us-east-1.on.aws/"
        self.client = AcidoClient(lambda_url=self.lambda_url)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.client.close()
    
    def test_init_with_url(self):
        """Test initialization with explicit URL."""
        client = AcidoClient(lambda_url=self.lambda_url)
        self.assertEqual(client.lambda_url, self.lambda_url)
        client.close()
    
    def test_init_with_env_var(self):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {'LAMBDA_FUNCTION_URL': self.lambda_url}):
            client = AcidoClient()
            self.assertEqual(client.lambda_url, self.lambda_url)
            client.close()
    
    def test_init_without_url(self):
        """Test initialization fails without URL."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AcidoClientError):
                AcidoClient()
    
    def test_url_normalization(self):
        """Test URL normalization adds trailing slash."""
        client = AcidoClient(lambda_url="https://test.lambda-url.us-east-1.on.aws")
        self.assertTrue(client.lambda_url.endswith('/'))
        client.close()
    
    @patch('acido_client.client.requests.Session.post')
    def test_fleet_operation(self, mock_post):
        """Test fleet operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'fleet',
                'instances': 2,
                'outputs': []
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.fleet(
            image="kali-rolling",
            targets=["merabytes.com", "uber.com"],
            task="nmap -iL input -p 0-1000"
        )
        
        self.assertEqual(result['operation'], 'fleet')
        self.assertEqual(result['instances'], 2)
        
        # Verify request was made with correct payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['operation'], 'fleet')
        self.assertEqual(payload['image'], 'kali-rolling')
        self.assertEqual(len(payload['targets']), 2)
    
    @patch('acido_client.client.requests.Session.post')
    def test_run_operation(self, mock_post):
        """Test run operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'run',
                'name': 'test-runner',
                'outputs': []
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.run(
            name="test-runner",
            image="github-runner",
            task="./run.sh"
        )
        
        self.assertEqual(result['operation'], 'run')
        self.assertEqual(result['name'], 'test-runner')
        
        # Verify request payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['operation'], 'run')
        self.assertEqual(payload['name'], 'test-runner')
        self.assertEqual(payload['duration'], 900)  # default value
    
    @patch('acido_client.client.requests.Session.post')
    def test_ls_operation(self, mock_post):
        """Test ls operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'ls',
                'instances': []
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.ls()
        
        self.assertEqual(result['operation'], 'ls')
        self.assertIn('instances', result)
    
    @patch('acido_client.client.requests.Session.post')
    def test_rm_operation(self, mock_post):
        """Test rm operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'rm',
                'result': {'removed': 'test-fleet'}
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.rm(name="test-fleet")
        
        self.assertEqual(result['operation'], 'rm')
        self.assertIn('result', result)
    
    @patch('acido_client.client.requests.Session.post')
    def test_ip_create_operation(self, mock_post):
        """Test ip_create operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'ip_create',
                'result': {'created': 'test-ip'}
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.ip_create(name="test-ip")
        
        self.assertEqual(result['operation'], 'ip_create')
        self.assertIn('result', result)
    
    @patch('acido_client.client.requests.Session.post')
    def test_ip_ls_operation(self, mock_post):
        """Test ip_ls operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'ip_ls',
                'ip_addresses': []
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.ip_ls()
        
        self.assertEqual(result['operation'], 'ip_ls')
        self.assertIn('ip_addresses', result)
    
    @patch('acido_client.client.requests.Session.post')
    def test_ip_rm_operation(self, mock_post):
        """Test ip_rm operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'ip_rm',
                'result': {'removed': 'test-ip', 'success': True}
            })
        }
        mock_post.return_value = mock_response
        
        result = self.client.ip_rm(name="test-ip")
        
        self.assertEqual(result['operation'], 'ip_rm')
        self.assertIn('result', result)
    
    @patch('acido_client.client.requests.Session.post')
    def test_error_handling(self, mock_post):
        """Test error handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Test error',
                'type': 'TestException'
            })
        }
        mock_post.return_value = mock_response
        
        with self.assertRaises(AcidoClientError) as ctx:
            self.client.ls()
        
        self.assertIn('Test error', str(ctx.exception))
    
    @patch('acido_client.client.requests.Session.post')
    def test_request_exception(self, mock_post):
        """Test handling of request exceptions."""
        mock_post.side_effect = Exception("Network error")
        
        with self.assertRaises(AcidoClientError) as ctx:
            self.client.ls()
        
        self.assertIn('Request failed', str(ctx.exception))
    
    def test_context_manager(self):
        """Test context manager protocol."""
        with AcidoClient(lambda_url=self.lambda_url) as client:
            self.assertIsNotNone(client)
            self.assertIsNotNone(client.session)


if __name__ == '__main__':
    unittest.main()
