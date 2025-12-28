import unittest
from unittest.mock import patch, MagicMock
from src.main import process_job
from src.models import Job

class TestMain(unittest.TestCase):

    @patch('src.main.AgentExecutor')
    @patch('src.main.update_status')
    def test_process_job(self, mock_update_status, mock_agent_executor):
        # Arrange
        job = Job(id='123', app_name='test-app', error_log='division by zero', log_id='456')
        mock_agent_executor.return_value.invoke.return_value = {"output": "Fixed"}

        # Act
        process_job(job)

        # Assert
        mock_update_status.run.assert_any_call(tool_input={"log_id": "456", "status": "processing"})
        mock_agent_executor.return_value.invoke.assert_called_once_with({
            "input": "Fix the error in the test-app application. Here is the error log: division by zero. You must provide the repo_path and branch_name as a single string, separated by a comma. The branch name should be descriptive of the fix being implemented. When calling the write_file function, you must provide both the file_path and the content arguments."
        })
        mock_update_status.run.assert_any_call(tool_input={"log_id": "456", "status": "completed"})

if __name__ == '__main__':
    unittest.main()
