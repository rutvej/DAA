import unittest
from unittest.mock import patch

from agent_src.tools.database_tool import AnalysisUpdater


class TestDatabaseTool(unittest.TestCase):
    @patch("agent_src.tools.database_tool._send_request")
    def test_update_status_processing(self, mock_send_request):
        # Arrange
        log_id = "123"
        updater = AnalysisUpdater(log_id)

        # Act
        updater.update_analysis_processing()

        # Assert
        mock_send_request.assert_called_once_with(
            {"log_id": log_id, "status": "processing"}
        )

    @patch("agent_src.tools.database_tool._send_request")
    def test_update_status_completed(self, mock_send_request):
        # Arrange
        log_id = "123"
        pr_url = "https://github.com/rutvej/checkout-service/pull/142"
        postmortem = "Some postmortem text"

        updater = AnalysisUpdater(log_id)
        updater.set_pull_request_url(pr_url)
        updater.set_postmortem(postmortem)

        # Act
        updater.update_analysis_completed()

        # Assert
        mock_send_request.assert_called_once_with(
            {
                "log_id": log_id,
                "status": "completed",
                "pull_request_url": pr_url,
                "postmortem": postmortem,
            }
        )


if __name__ == "__main__":
    unittest.main()
