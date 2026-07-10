import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import timezone

from agent_src.log_connectors import (
    parse_timestamp,
    get_configured_connector,
    AWSCloudWatchConnector,
    GCPCloudLoggingConnector,
    DatadogConnector
)


class TestLogConnectors(unittest.TestCase):

    def test_parse_timestamp_iso(self):
        ts = parse_timestamp("2026-07-08T19:26:03Z")
        self.assertEqual(ts.year, 2026)
        self.assertEqual(ts.month, 7)
        self.assertEqual(ts.day, 8)
        self.assertEqual(ts.hour, 19)
        self.assertEqual(ts.minute, 26)
        self.assertEqual(ts.second, 3)
        self.assertEqual(ts.tzinfo, timezone.utc)

    def test_parse_timestamp_unix_seconds(self):
        ts = parse_timestamp("1783538763")  # Some timestamp
        self.assertEqual(ts.tzinfo, timezone.utc)
        self.assertAlmostEqual(ts.timestamp(), 1783538763.0)

    def test_parse_timestamp_unix_milliseconds(self):
        ts = parse_timestamp("1783538763000")  # Some timestamp in ms
        self.assertEqual(ts.tzinfo, timezone.utc)
        self.assertAlmostEqual(ts.timestamp(), 1783538763.0)

    def test_get_configured_connector_none(self):
        with patch.dict(os.environ, {}, clear=True):
            connector = get_configured_connector()
            self.assertIsNone(connector)

    @patch.dict(os.environ, {
        "AWS_ACCESS_KEY_ID": "mock_id",
        "AWS_SECRET_ACCESS_KEY": "mock_secret"
    }, clear=True)
    def test_get_configured_connector_aws(self):
        connector = get_configured_connector()
        self.assertIsInstance(connector, AWSCloudWatchConnector)

    @patch.dict(os.environ, {
        "GCP_PROJECT_ID": "mock_project"
    }, clear=True)
    def test_get_configured_connector_gcp(self):
        connector = get_configured_connector()
        self.assertIsInstance(connector, GCPCloudLoggingConnector)

    @patch.dict(os.environ, {
        "DD_API_KEY": "mock_api",
        "DD_APP_KEY": "mock_app"
    }, clear=True)
    def test_get_configured_connector_datadog(self):
        connector = get_configured_connector()
        self.assertIsInstance(connector, DatadogConnector)

    @patch.dict(os.environ, {
        "AWS_ACCESS_KEY_ID": "mock_id",
        "AWS_SECRET_ACCESS_KEY": "mock_secret"
    }, clear=True)
    def test_aws_connector_fetch(self):
        # Setup mock boto3 logs client
        import sys
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/ecs/test-service"}]
        }
        mock_client.filter_log_events.return_value = {
            "events": [
                {"timestamp": 100, "message": "Log line 1"},
                {"timestamp": 200, "message": "Log line 2"}
            ]
        }

        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            conn = AWSCloudWatchConnector()
            logs = conn.fetch_logs("test-service", "2026-07-08T19:26:03Z")
            self.assertEqual(logs, "Log line 1\nLog line 2")
            mock_client.filter_log_events.assert_called_once()

    @patch.dict(os.environ, {
        "GCP_PROJECT_ID": "mock_project",
        "GCP_ACCESS_TOKEN": "mock_token"
    }, clear=True)
    @patch("requests.post")
    def test_gcp_connector_fetch_rest_fallback(self, mock_post):
        # Mock requests.post for GCP Logging REST API
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "entries": [
                {"textPayload": "GCP line 1"},
                {"jsonPayload": {"message": "GCP line 2"}}
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        # Force gcp_logging import error (no google-cloud-logging library installed)
        with patch.dict("sys.modules", {"google.cloud": None}):
            conn = GCPCloudLoggingConnector()
            logs = conn.fetch_logs("test-service", "2026-07-08T19:26:03Z")
            self.assertEqual(logs, "GCP line 1\nGCP line 2")
            mock_post.assert_called_once()

    @patch.dict(os.environ, {
        "DD_API_KEY": "mock_api",
        "DD_APP_KEY": "mock_app"
    }, clear=True)
    @patch("requests.post")
    def test_datadog_connector_fetch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"attributes": {"message": "Datadog log 1"}},
                {"attributes": {"message": "Datadog log 2"}}
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        conn = DatadogConnector()
        logs = conn.fetch_logs("test-service", "2026-07-08T19:26:03Z")
        self.assertEqual(logs, "Datadog log 1\nDatadog log 2")
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
