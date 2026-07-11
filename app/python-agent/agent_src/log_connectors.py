import os
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)


def parse_timestamp(ts_str: str) -> datetime:
    """Parses ISO-8601, millisecond or second Unix timestamps, returning timezone-aware datetime."""
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        val = float(ts_str)
        if val > 2e9:  # MS timestamp
            return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(val, tz=timezone.utc)
    except ValueError:
        pass

    # Strip 'Z' if present
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Fallback parsing for common custom formats
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return datetime.now(timezone.utc)


class BaseLogConnector:
    """Base interface for all cloud log ingestion connectors."""

    def is_configured(self) -> bool:
        """Returns True if the required environment credentials for this connector are configured."""
        raise NotImplementedError

    def fetch_logs(
        self, app_name: str, timestamp_str: str, limit: int = 500
    ) -> Optional[str]:
        """Fetches up to `limit` log lines before/around the incident timestamp.

        Returns a plain-text string of log lines, or None if fetching fails.
        """
        raise NotImplementedError


class AWSCloudWatchConnector(BaseLogConnector):
    """Log connector for AWS CloudWatch Logs."""

    def is_configured(self) -> bool:
        return bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            and os.environ.get("AWS_SECRET_ACCESS_KEY")
        )

    def fetch_logs(
        self, app_name: str, timestamp_str: str, limit: int = 500
    ) -> Optional[str]:
        logger.info(
            "AWS CloudWatch Log Connector fetching logs for %s near %s",
            app_name,
            timestamp_str,
        )
        try:
            import boto3
        except ImportError:
            logger.warning(
                "boto3 is not installed. AWS credentials are present, but cannot fetch real logs from CloudWatch. Falling back."
            )
            return None

        try:
            ts = parse_timestamp(timestamp_str)
            # AWS expects epoch milliseconds.
            # We want logs from 15 minutes before the incident to 1 minute after.
            start_time = int((ts - timedelta(minutes=15)).timestamp() * 1000)
            end_time = int((ts + timedelta(minutes=1)).timestamp() * 1000)

            aws_region = (
                os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION")
                or "us-east-1"
            )
            client = boto3.client(
                "logs",
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=aws_region,
            )

            # Standard naming convention: look for a log group matching app_name
            log_group_name = app_name
            try:
                groups_resp = client.describe_log_groups(logGroupNamePrefix=app_name)
                groups = groups_resp.get("logGroups", [])
                if groups:
                    log_group_name = groups[0]["logGroupName"]
            except Exception as e:
                logger.warning(
                    "Could not search log group prefix %s: %s. Using app_name directly.",
                    app_name,
                    e,
                )

            # Query the logs using filter_log_events
            events_resp = client.filter_log_events(
                logGroupName=log_group_name,
                startTime=start_time,
                endTime=end_time,
                limit=limit,
            )

            events = events_resp.get("events", [])
            events.sort(key=lambda x: x.get("timestamp", 0))

            lines = [event.get("message", "").rstrip() for event in events]
            if not lines:
                return f"[AWS CloudWatch: No logs found in group '{log_group_name}' between {ts - timedelta(minutes=15)} and {ts + timedelta(minutes=1)}]"

            return "\n".join(lines)
        except Exception as e:
            logger.error("AWS CloudWatch Log Connector failed to fetch logs: %s", e)
            return None


class GCPCloudLoggingConnector(BaseLogConnector):
    """Log connector for GCP Cloud Logging."""

    def is_configured(self) -> bool:
        return bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )

    def fetch_logs(
        self, app_name: str, timestamp_str: str, limit: int = 500
    ) -> Optional[str]:
        logger.info(
            "GCP Cloud Logging Connector fetching logs for %s near %s",
            app_name,
            timestamp_str,
        )

        try:
            from google.cloud import logging as gcp_logging

            gcp_available = True
        except ImportError:
            gcp_available = False

        ts = parse_timestamp(timestamp_str)
        start_time_iso = (ts - timedelta(minutes=15)).isoformat()
        end_time_iso = (ts + timedelta(minutes=1)).isoformat()

        gcp_filter = f'resource.type="k8s_container" OR resource.type="gce_instance" OR logName:"{app_name}" AND timestamp >= "{start_time_iso}" AND timestamp <= "{end_time_iso}"'

        if gcp_available:
            try:
                cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
                    "GOOGLE_CLOUD_PROJECT"
                )

                if cred_path:
                    client = gcp_logging.Client.from_service_account_json(cred_path)
                elif project_id:
                    client = gcp_logging.Client(project=project_id)
                else:
                    client = gcp_logging.Client()

                entries = client.list_entries(filter_=gcp_filter, page_size=limit)

                lines = []
                for entry in entries:
                    payload = entry.payload
                    if isinstance(payload, dict):
                        msg = (
                            payload.get("message") or payload.get("log") or str(payload)
                        )
                    else:
                        msg = str(payload)
                    lines.append(msg.rstrip())
                    if len(lines) >= limit:
                        break

                if not lines:
                    return f"[GCP Cloud Logging: No logs found matching filter '{gcp_filter}']"
                return "\n".join(lines)
            except Exception as e:
                logger.error(
                    "GCP Cloud Logging client failed: %s. Trying REST API fallback...",
                    e,
                )

        # Fallback to direct REST API if client library is not present or failed
        try:
            project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
                "GOOGLE_CLOUD_PROJECT"
            )
            if not project_id and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                try:
                    import json

                    with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], "r") as f:
                        data = json.load(f)
                        project_id = data.get("project_id")
                except Exception:
                    pass

            if not project_id:
                logger.warning(
                    "GCP Project ID not found, unable to call GCP Logging REST API."
                )
                return None

            url = "https://logging.googleapis.com/v2/entries:list"
            try:
                import google.auth
                import google.auth.transport.requests as google_requests

                credentials, project = google.auth.default()
                request = google_requests.Request()
                credentials.refresh(request)
                token = credentials.token
            except Exception:
                token = os.environ.get("GCP_ACCESS_TOKEN")

            if not token:
                logger.warning("GCP Access Token not available for REST API fallback.")
                return None

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            body = {
                "resourceNames": [f"projects/{project_id}"],
                "filter": gcp_filter,
                "orderBy": "timestamp asc",
                "pageSize": limit,
            }
            resp = requests.post(url, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("entries", [])
            lines = []
            for entry in entries:
                payload = (
                    entry.get("jsonPayload")
                    or entry.get("textPayload")
                    or entry.get("protoPayload")
                )
                if isinstance(payload, dict):
                    msg = payload.get("message") or payload.get("log") or str(payload)
                else:
                    msg = str(payload)
                lines.append(msg.rstrip())

            if not lines:
                return f"[GCP Cloud Logging REST API: No logs found matching filter '{gcp_filter}']"
            return "\n".join(lines)
        except Exception as e:
            logger.error("GCP Cloud Logging REST API fallback failed: %s", e)
            return None


class DatadogConnector(BaseLogConnector):
    """Log connector for Datadog Logs API."""

    def is_configured(self) -> bool:
        return bool(
            (os.environ.get("DD_API_KEY") or os.environ.get("DATADOG_API_KEY"))
            and (os.environ.get("DD_APP_KEY") or os.environ.get("DATADOG_APP_KEY"))
        )

    def fetch_logs(
        self, app_name: str, timestamp_str: str, limit: int = 500
    ) -> Optional[str]:
        logger.info(
            "Datadog Log Connector fetching logs for %s near %s",
            app_name,
            timestamp_str,
        )
        try:
            api_key = os.environ.get("DD_API_KEY") or os.environ.get("DATADOG_API_KEY")
            app_key = os.environ.get("DD_APP_KEY") or os.environ.get("DATADOG_APP_KEY")
            site = os.environ.get("DD_SITE") or "datadoghq.com"

            ts = parse_timestamp(timestamp_str)
            start_time = (ts - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            end_time = (ts + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

            url = f"https://api.{site}/api/v2/logs/events/search"
            headers = {
                "DD-API-KEY": api_key,
                "DD-APPLICATION-KEY": app_key,
                "Content-Type": "application/json",
            }
            body = {
                "filter": {
                    "query": f"service:{app_name} OR host:{app_name} OR {app_name}",
                    "from": start_time,
                    "to": end_time,
                },
                "page": {"limit": limit},
                "sort": "timestamp",
            }
            resp = requests.post(url, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            events = data.get("data", [])

            lines = []
            for event in events:
                attributes = event.get("attributes", {})
                message = attributes.get("message") or attributes.get("message_text")
                if message:
                    lines.append(message.rstrip())
                else:
                    lines.append(str(attributes))

            if not lines:
                return f"[Datadog: No logs found for service '{app_name}' between {start_time} and {end_time}]"

            return "\n".join(lines)
        except Exception as e:
            logger.error("Datadog Log Connector failed to fetch logs: %s", e)
            return None


def get_configured_connector() -> Optional[BaseLogConnector]:
    """Inspects environment credentials and returns the first configured log connector, or None."""
    connectors = [
        DatadogConnector(),
        GCPCloudLoggingConnector(),
        AWSCloudWatchConnector(),
    ]
    for conn in connectors:
        if conn.is_configured():
            logger.info("Found configured log connector: %s", conn.__class__.__name__)
            return conn
    return None
