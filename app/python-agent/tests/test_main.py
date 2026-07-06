import unittest
import uuid
from unittest.mock import patch, MagicMock
from src.main import process_job
from src.models import Job, ErrorLog

class TestMain(unittest.TestCase):

    @patch('src.main.AgentExecutor')
    @patch('src.main.get_llm')
    @patch('src.main.AnalysisUpdater')
    def test_process_job(self, mock_analysis_updater, mock_get_llm, mock_agent_executor):
        # Arrange
        job_id = uuid.uuid4()
        log_id = uuid.uuid4()
        error_log_id = uuid.uuid4()
        
        error_log = ErrorLog(
            id=error_log_id,
            app_name='test-app',
            content='division by zero',
            stack_trace='ZeroDivisionError: division by zero',
            timestamp='2026-07-05T14:00:00'
        )
        
        job = Job(
            id=job_id,
            log_id=log_id,
            app_name='test-app',
            status='pending',
            created_at='2026-07-05T14:00:00',
            updated_at='2026-07-05T14:00:00',
            error_log=error_log
        )
        
        mock_agent_executor.return_value.invoke.return_value = {"output": "PR_URL: http://github.com/pr/1\nPOSTMORTEM:\nSome report"}
        
        mock_updater_instance = mock_analysis_updater.return_value

        # Act
        process_job(job)

        # Assert
        mock_analysis_updater.assert_called_once_with(log_id)
        mock_updater_instance.update_analysis_processing.assert_called_once()
        mock_agent_executor.return_value.invoke.assert_called_once_with({
            "input": f"Investigate across all 4 dimensions and remediate the outage in test-app. Here is the scrubbed error log: {error_log}."
        })
        mock_updater_instance.set_pull_request_url.assert_called_once_with('http://github.com/pr/1')
        mock_updater_instance.set_postmortem.assert_called_once_with('Some report')
        mock_updater_instance.update_analysis_completed.assert_called_once()

if __name__ == '__main__':
    unittest.main()
