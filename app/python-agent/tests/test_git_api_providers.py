import unittest
from unittest.mock import patch

from agent_src.tools.git_api_providers import (
    BitbucketProvider,
    GitLabProvider,
    build_project_connection,
    create_provider_client,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload


class TestGitApiProviders(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "DAA_REPO_URL": "https://bitbucket.org/acme/payment-api.git",
            "DAA_REPO_PROVIDER": "bitbucket",
            "DAA_GIT_TOKEN": "token",
        },
        clear=False,
    )
    @patch("agent_src.tools.git_api_providers.requests.request")
    def test_create_provider_client_selects_bitbucket(self, mock_request):
        mock_request.return_value = FakeResponse(payload={"mainbranch": {"name": "main"}})

        client = create_provider_client("payment-api")

        self.assertIsInstance(client, BitbucketProvider)
        self.assertEqual(client.default_branch, "main")
        self.assertEqual(client.api_base, "https://api.bitbucket.org/2.0/repositories/acme/payment-api")

    @patch.dict(
        "os.environ",
        {
            "DAA_REPO_URL": "https://gitlab.example.com/group/subgroup/payment-api.git",
            "DAA_REPO_PROVIDER": "gitlab",
            "DAA_GIT_TOKEN": "token",
        },
        clear=False,
    )
    @patch("agent_src.tools.git_api_providers.requests.request")
    def test_gitlab_default_branch_comes_from_repo_metadata(self, mock_request):
        mock_request.return_value = FakeResponse(payload={"default_branch": "develop"})

        client = create_provider_client("payment-api")

        self.assertIsInstance(client, GitLabProvider)
        self.assertEqual(client.default_branch, "develop")
        self.assertTrue(client.api_base.endswith("/api/v4/projects/group%2Fsubgroup%2Fpayment-api"))

    def test_build_project_connection_uses_env_repo(self):
        with patch.dict(
            "os.environ",
            {
                "DAA_REPO_URL": "https://github.com/acme/payment-api.git",
                "DAA_REPO_PROVIDER": "github",
                "DAA_GIT_TOKEN": "token",
            },
            clear=False,
        ):
            conn = build_project_connection("payment-api")

        self.assertEqual(conn["repo_provider"], "github")
        self.assertEqual(conn["repo_url"], "https://github.com/acme/payment-api.git")


if __name__ == "__main__":
    unittest.main()
