import unittest
import uuid
from unittest.mock import patch

from agent_src.main import process_job, scrub_secrets
from agent_src.models import ErrorLog, Job


class TestMain(unittest.TestCase):
    @patch("agent_src.orchestrator.run_preflight")
    @patch("agent_src.main.AgentExecutor")
    @patch("agent_src.main.get_llm")
    @patch("agent_src.main.AnalysisUpdater")
    def test_process_job_daa20_fallback(
        self,
        mock_analysis_updater,
        mock_get_llm,
        mock_agent_executor,
        mock_run_preflight,
    ):
        # Arrange
        mock_run_preflight.side_effect = Exception("Simulated pre-flight failure")
        job_id = uuid.uuid4()
        log_id = uuid.uuid4()
        error_log_id = uuid.uuid4()

        error_log = ErrorLog(
            id=error_log_id,
            app_name="test-app",
            content="division by zero",
            stack_trace="ZeroDivisionError: division by zero",
            timestamp="2026-07-05T14:00:00",
        )

        job = Job(
            id=job_id,
            log_id=log_id,
            app_name="test-app",
            status="pending",
            created_at="2026-07-05T14:00:00",
            updated_at="2026-07-05T14:00:00",
            error_log=error_log,
        )

        mock_agent_executor.return_value.invoke.return_value = {
            "output": "PR_URL: http://github.com/pr/1\nPOSTMORTEM:\nSome report"
        }
        mock_updater_instance = mock_analysis_updater.return_value

        # Act
        process_job(job)

        # Assert
        mock_analysis_updater.assert_called_once_with(log_id)
        mock_updater_instance.update_analysis_processing.assert_called_once()
        called_args, called_kwargs = mock_agent_executor.return_value.invoke.call_args
        scrubbed_log = scrub_secrets(str(error_log))
        self.assertEqual(
            called_args[0]["input"],
            f"Investigate across all 4 dimensions and remediate the outage in test-app. Error: {scrubbed_log}",
        )
        mock_updater_instance.set_pull_request_url.assert_called_once_with(
            "http://github.com/pr/1"
        )
        mock_updater_instance.set_postmortem.assert_called_once_with("Some report")
        mock_updater_instance.update_analysis_completed.assert_called_once()

    @patch("agent_src.orchestrator.RepoCacheManager")
    @patch("agent_src.orchestrator.PostflightOrchestrator")
    @patch("agent_src.orchestrator.run_preflight")
    @patch("agent_src.agent_safety.AgentSafetyWrapper")
    @patch("agent_src.main.get_llm")
    @patch("agent_src.main.AnalysisUpdater")
    def test_process_job_daa30(
        self,
        mock_analysis_updater,
        mock_get_llm,
        mock_safety_wrapper,
        mock_run_preflight,
        mock_postflight,
        mock_repo_cache,
    ):
        # Arrange
        mock_run_preflight.return_value = {
            "skip": False,
            "worktree_path": "/tmp/worktree-test",
            "context": "[INCIDENT]\napp: test-app\nfingerprint: mock_fingerprint\n",
            "fingerprint": "mock_fingerprint",
        }
        mock_postflight.return_value.run.return_value = {
            "pr_url": "http://github.com/pr/1",
            "postmortem": "Some report",
        }

        job_id = uuid.uuid4()
        log_id = uuid.uuid4()
        error_log_id = uuid.uuid4()

        error_log = ErrorLog(
            id=error_log_id,
            app_name="test-app",
            content="division by zero",
            stack_trace="ZeroDivisionError: division by zero",
            timestamp="2026-07-05T14:00:00",
        )

        job = Job(
            id=job_id,
            log_id=log_id,
            app_name="test-app",
            status="pending",
            created_at="2026-07-05T14:00:00",
            updated_at="2026-07-05T14:00:00",
            error_log=error_log,
        )

        mock_safety_wrapper.return_value.invoke.return_value = {
            "output": "WRITE_DIFF:\n--- a/file\n+++ b/file\nEXPLANATION: Fix"
        }
        mock_updater_instance = mock_analysis_updater.return_value

        # Act
        process_job(job)

        # Assert
        mock_analysis_updater.assert_called_once_with(log_id)
        mock_updater_instance.update_analysis_processing.assert_called_once()
        called_args, called_kwargs = mock_safety_wrapper.return_value.invoke.call_args
        self.assertEqual(
            called_args[0]["input"],
            "[INCIDENT]\napp: test-app\nfingerprint: mock_fingerprint\n",
        )
        mock_updater_instance.set_pull_request_url.assert_called_once_with(
            "http://github.com/pr/1"
        )
        mock_updater_instance.set_postmortem.assert_called_once_with("Some report")
        mock_updater_instance.update_analysis_completed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
