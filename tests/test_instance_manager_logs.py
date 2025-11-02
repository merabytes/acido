"""
Unit tests for InstanceManager container log retrieval.

Tests the new SDK-based container log retrieval method.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Set required environment variables for tests BEFORE importing any acido modules
os.environ['AZURE_TENANT_ID'] = 'test-tenant-id'
os.environ['AZURE_CLIENT_ID'] = 'test-client-id'
os.environ['AZURE_CLIENT_SECRET'] = 'test-secret'
os.environ['AZURE_RESOURCE_GROUP'] = 'test-rg'

# Mock sys.argv to prevent argparse from processing test args
_original_argv = sys.argv
sys.argv = ['test']


class TestInstanceManagerLogs(unittest.TestCase):
    """Test cases for InstanceManager container log retrieval."""

    @patch('acido.azure_utils.InstanceManager.ContainerInstanceManagementClient')
    def test_get_container_logs_success(self, mock_client_class):
        """Test successful container log retrieval."""
        from acido.azure_utils.InstanceManager import InstanceManager
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup mock for list_logs
        mock_logs = MagicMock()
        mock_logs.content = 'Log line 1\nLog line 2\ncommand: test-uuid-123\n'
        mock_client.containers.list_logs.return_value = mock_logs
        
        # Create InstanceManager with login=False to skip authentication
        im = InstanceManager(resource_group='test-rg', login=False)
        im._client = mock_client
        
        # Call get_container_logs
        logs = im.get_container_logs(
            container_group_name='test-cg',
            container_name='test-container'
        )
        
        # Verify the method was called correctly
        mock_client.containers.list_logs.assert_called_once_with(
            resource_group_name='test-rg',
            container_group_name='test-cg',
            container_name='test-container',
            tail=None,
            timestamps=False
        )
        
        # Verify logs content
        self.assertEqual(logs, 'Log line 1\nLog line 2\ncommand: test-uuid-123\n')

    @patch('acido.azure_utils.InstanceManager.ContainerInstanceManagementClient')
    def test_get_container_logs_with_tail(self, mock_client_class):
        """Test container log retrieval with tail parameter."""
        from acido.azure_utils.InstanceManager import InstanceManager
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup mock for list_logs
        mock_logs = MagicMock()
        mock_logs.content = 'Last 10 log lines\n'
        mock_client.containers.list_logs.return_value = mock_logs
        
        # Create InstanceManager with login=False to skip authentication
        im = InstanceManager(resource_group='test-rg', login=False)
        im._client = mock_client
        
        # Call get_container_logs with tail
        logs = im.get_container_logs(
            container_group_name='test-cg',
            container_name='test-container',
            tail=10,
            timestamps=True
        )
        
        # Verify the method was called with correct parameters
        mock_client.containers.list_logs.assert_called_once_with(
            resource_group_name='test-rg',
            container_group_name='test-cg',
            container_name='test-container',
            tail=10,
            timestamps=True
        )
        
        # Verify logs content
        self.assertEqual(logs, 'Last 10 log lines\n')

    @patch('acido.azure_utils.InstanceManager.ContainerInstanceManagementClient')
    def test_get_container_logs_error(self, mock_client_class):
        """Test container log retrieval with error."""
        from acido.azure_utils.InstanceManager import InstanceManager
        from azure.core.exceptions import HttpResponseError
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup mock to raise HttpResponseError
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.containers.list_logs.side_effect = HttpResponseError(
            message="Container not found",
            response=mock_response
        )
        
        # Create InstanceManager with login=False to skip authentication
        im = InstanceManager(resource_group='test-rg', login=False)
        im._client = mock_client
        
        # Call get_container_logs and expect exception
        with self.assertRaises(HttpResponseError):
            im.get_container_logs(
                container_group_name='test-cg',
                container_name='test-container'
            )


class TestWaitCommandWithSDK(unittest.TestCase):
    """Test cases for wait_command using SDK."""

    def test_wait_command_with_instance_manager(self):
        """Test wait_command with instance_manager parameter."""
        from acido.utils.shell_utils import wait_command
        
        # Mock instance_manager
        mock_im = MagicMock()
        mock_im.get_container_logs.return_value = 'Starting...\nRunning...\ncommand: uuid-12345\n'
        
        # Call wait_command with instance_manager
        cont, command_uuid, exception = wait_command(
            rg='test-rg',
            cg='test-cg',
            cont='test-container',
            wait=None,
            instance_manager=mock_im
        )
        
        # Verify results
        self.assertEqual(cont, 'test-container')
        self.assertEqual(command_uuid, 'uuid-12345')
        self.assertIsNone(exception)
        
        # Verify get_container_logs was called
        self.assertTrue(mock_im.get_container_logs.called)

    def test_wait_command_timeout(self):
        """Test wait_command with timeout."""
        from acido.utils.shell_utils import wait_command
        
        # Mock instance_manager that returns logs without command UUID
        mock_im = MagicMock()
        mock_im.get_container_logs.return_value = 'Still running...\n'
        
        # Call wait_command with short timeout
        cont, command_uuid, exception = wait_command(
            rg='test-rg',
            cg='test-cg',
            cont='test-container',
            wait=1,  # 1 second timeout
            instance_manager=mock_im
        )
        
        # Verify results
        self.assertEqual(cont, 'test-container')
        self.assertIsNone(command_uuid)
        self.assertEqual(exception, 'TIMEOUT REACHED')

    def test_wait_command_exception_in_logs(self):
        """Test wait_command when exception appears in logs."""
        from acido.utils.shell_utils import wait_command
        
        # Mock instance_manager that returns logs with exception
        mock_im = MagicMock()
        mock_im.get_container_logs.return_value = 'Exception: Something went wrong\n'
        
        # Call wait_command
        cont, command_uuid, exception = wait_command(
            rg='test-rg',
            cg='test-cg',
            cont='test-container',
            wait=None,
            instance_manager=mock_im
        )
        
        # Verify results
        self.assertEqual(cont, 'test-container')
        self.assertIsNone(command_uuid)
        self.assertIn('Exception', exception)

    def test_wait_command_sdk_error(self):
        """Test wait_command when SDK raises an error."""
        from acido.utils.shell_utils import wait_command
        from azure.core.exceptions import HttpResponseError
        
        # Mock instance_manager that raises an error
        mock_im = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_im.get_container_logs.side_effect = HttpResponseError(
            message="Internal server error",
            response=mock_response
        )
        
        # Call wait_command
        cont, command_uuid, exception = wait_command(
            rg='test-rg',
            cg='test-cg',
            cont='test-container',
            wait=None,
            instance_manager=mock_im
        )
        
        # Verify results
        self.assertEqual(cont, 'test-container')
        self.assertIsNone(command_uuid)
        self.assertIsNotNone(exception)
        self.assertIn('Failed to retrieve', exception)


if __name__ == '__main__':
    # Restore original argv
    sys.argv = _original_argv
    unittest.main()
