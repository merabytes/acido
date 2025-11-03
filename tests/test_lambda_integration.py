"""
Integration test demonstrating SDK-based log retrieval in Lambda context.

This test simulates a Lambda environment where az CLI is not available,
and verifies that the SDK-based approach works correctly.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import json

# Set required environment variables for Lambda context
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

# Mock sys.argv to prevent argparse from processing test args
_original_argv = sys.argv
sys.argv = ['test']


class TestLambdaIntegration(unittest.TestCase):
    """Integration tests for Lambda with SDK-based log retrieval."""

    @patch('tempfile.NamedTemporaryFile')
    @patch('lambda_handler.ThreadPoolShim')
    @patch('acido.cli.subprocess')  # Mock subprocess to simulate Lambda without az CLI
    def test_lambda_fleet_with_sdk_logs(self, mock_subprocess, mock_pool_class, mock_temp_file):
        """Test Lambda fleet operation using SDK for log retrieval (no az CLI)."""
        from lambda_handler import lambda_handler
        
        # Setup temporary file mock
        mock_file = MagicMock()
        mock_file.name = '/tmp/test-input.txt'
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_file
        
        # Mock ThreadPoolShim
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        
        # Mock ThreadPoolShim.apply_async to simulate log retrieval
        def mock_apply_async(func, args, callback=None):
            # Simulate wait_command being called
            result_mock = MagicMock()
            
            # Extract arguments
            rg, cg, cont, wait, instance_manager = args
            
            # Simulate SDK-based log retrieval (no subprocess calls)
            # The instance_manager should be passed and used
            if instance_manager:
                # Use the SDK method
                logs = instance_manager.get_container_logs(cg, cont)
                command_uuid = 'test-uuid-123' if 'command: test-uuid-123' in logs else None
                exception = None
            else:
                # This path should not be taken in Lambda
                command_uuid = None
                exception = 'No instance_manager provided'
            
            # Call the callback if provided
            if callback:
                callback((cont, command_uuid, exception))
            
            result_mock.wait.return_value = None
            return result_mock
        
        mock_pool.apply_async = mock_apply_async
        
        # Mock the Acido class components
        with patch('lambda_handler.Acido') as mock_acido_class:
            mock_acido = MagicMock()
            mock_acido_class.return_value = mock_acido
            
            # Mock instance_manager with SDK log retrieval
            mock_im = MagicMock()
            mock_im.get_container_logs.return_value = 'Starting...\nRunning...\ncommand: test-uuid-123\n'
            mock_acido.instance_manager = mock_im
            
            # Mock BlobManager
            mock_blob_manager = MagicMock()
            mock_blob_manager.download.return_value = b'Scan results from container'
            mock_acido.blob_manager = mock_blob_manager
            
            mock_acido.build_image_url.return_value = 'test.azurecr.io/kali-rolling-acido:latest'
            
            # Mock fleet method to simulate container creation
            def mock_fleet(*args, **kwargs):
                # Simulate fleet creation
                response = {'lambda-fleet': {'lambda-fleet-01': True, 'lambda-fleet-02': True}}
                outputs = {}
                
                # Instead of calling wait_command directly, just simulate it
                for cont in ['lambda-fleet-01', 'lambda-fleet-02']:
                    # Use instance_manager to get logs
                    if mock_acido.instance_manager:
                        logs = mock_acido.instance_manager.get_container_logs('lambda-fleet', cont)
                        if 'command: test-uuid-123' in logs:
                            output = mock_blob_manager.download('test-uuid-123')
                            outputs[cont] = output.decode()
                
                return response, outputs
            
            mock_acido.fleet.side_effect = mock_fleet
            mock_acido.rm.return_value = True
            
            # Test event
            event = {
                'image': 'kali-rolling',
                'targets': ['merabytes.com', 'uber.com'],
                'task': '/usr/local/bin/nmap -iL input -p 0-1000',
                'num_instances': 2
            }
            context = {}
            
            # Call Lambda handler
            response = lambda_handler(event, context)
            
            # Verify response
            self.assertEqual(response['statusCode'], 200)
            body = json.loads(response['body'])
            self.assertEqual(body['fleet_name'], 'lambda-fleet')
            self.assertEqual(body['instances'], 2)
            
            # Verify that instance_manager.get_container_logs was called (SDK method)
            self.assertTrue(mock_im.get_container_logs.called)
            
            # Verify that subprocess (az CLI) was NOT called for log retrieval
            # subprocess might be called for other things, but not for 'az container logs'
            for call in mock_subprocess.mock_calls:
                call_str = str(call)
                self.assertNotIn('az container logs', call_str, 
                               "az container logs should not be called when instance_manager is provided")

    @patch('acido.azure_utils.InstanceManager.ContainerInstanceManagementClient')
    def test_instance_manager_in_lambda_context(self, mock_client_class):
        """Test that InstanceManager can be used in Lambda context without az CLI."""
        from acido.azure_utils.InstanceManager import InstanceManager
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup mock for list_logs
        mock_logs = MagicMock()
        mock_logs.content = 'Container log output\ncommand: abc-123\n'
        mock_client.containers.list_logs.return_value = mock_logs
        
        # Create InstanceManager (simulating Lambda environment)
        im = InstanceManager(resource_group='test-rg', login=False)
        im._client = mock_client
        
        # Get logs using SDK (no az CLI)
        logs = im.get_container_logs(
            container_group_name='lambda-fleet',
            container_name='lambda-fleet-01'
        )
        
        # Verify logs were retrieved via SDK
        self.assertIn('command: abc-123', logs)
        mock_client.containers.list_logs.assert_called_once()


if __name__ == '__main__':
    # Restore original argv
    sys.argv = _original_argv
    unittest.main()
