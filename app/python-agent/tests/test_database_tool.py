import unittest
from unittest.mock import patch
from src.tools.database_tool import update_status, update_pull_request

class TestDatabaseTool(unittest.TestCase):

    @patch('src.tools.database_tool._send_request')
    def test_update_status(self, mock_send_request):
        # Arrange
        log_id = '123'
        status = 'processing'
        
        # Act
        update_status.run(tool_input={'log_id': log_id, 'status': status})

        # Assert
        mock_send_request.assert_called_once_with(log_id, {"status": status})

    @patch('src.tools.database_tool._send_request')
    def test_update_pull_request(self, mock_send_request):
        # Arrange
        log_id = '123'
        pull_request = 'https://gitlab.com/test/pull/1'

        # Act
        update_pull_request.run(tool_input={'log_id': log_id, 'pull_request_url': pull_request})

        # Assert
        mock_send_request.assert_called_once_with(log_id, {"pull_request_url": pull_request})

if __name__ == '__main__':
    unittest.main()
