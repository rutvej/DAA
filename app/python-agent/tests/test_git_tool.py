import json
import unittest
from unittest.mock import MagicMock, patch

from agent_src.tools.git_tool import (
    clone_repo,
    commit,
    create_branch,
    create_pull_request,
    get_project_connection,
    push,
)


class TestGitTool(unittest.TestCase):
    def setUp(self):
        import os

        self.old_env = dict(os.environ)
        os.environ["GITLAB_USER"] = "root"
        os.environ["GITLAB_HOST"] = "gitlab"
        if "GITLAB_PRIVATE_TOKEN" in os.environ:
            del os.environ["GITLAB_PRIVATE_TOKEN"]

    def tearDown(self):
        import os

        os.environ.clear()
        os.environ.update(self.old_env)

    def test_get_project_connection_stateless_fallback(self):
        import os

        os.environ["GIT_HOST"] = "http://host.docker.internal:3000"
        os.environ["GIT_ORG"] = "daa-admin"

        conn = get_project_connection("payment-api")

        self.assertEqual(
            conn["repo_url"],
            "http://host.docker.internal:3000/daa-admin/payment-api.git",
        )
        self.assertEqual(conn["repo_provider"], "gitea")

    @patch("agent_src.tools.git_tool.os.path.exists", return_value=False)
    @patch("agent_src.tools.git_tool.git.Repo")
    def test_clone_repo(self, mock_repo, mock_exists):
        # Arrange
        app_name = "test-app"
        expected_path = f"/tmp/{app_name}"
        mock_repo_instance = MagicMock()
        mock_repo.clone_from.return_value = mock_repo_instance

        # Act
        result = clone_repo.run(app_name)

        # Assert
        self.assertEqual(result, expected_path)
        mock_repo.clone_from.assert_called_once_with(
            "http://root:None@gitlab:80/root/test-app.git",
            expected_path,
            multi_options=["--"],
        )
        mock_repo_instance.config_writer.assert_called_once()

    @patch("agent_src.tools.git_tool.os.path.exists", return_value=True)
    @patch("agent_src.tools.git_tool._get_repo")
    def test_clone_repo_updates_existing_remote(self, mock_get_repo, mock_exists):
        app_name = "test-app"
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        result = clone_repo.run(app_name)

        self.assertEqual(result, f"/tmp/{app_name}")
        mock_get_repo.assert_called_once_with(f"/tmp/{app_name}")
        mock_repo.remotes.origin.set_url.assert_called_once_with(
            "http://root:None@gitlab:80/root/test-app.git"
        )

    @patch("agent_src.tools.git_tool._get_repo")
    def test_create_branch(self, mock_get_repo):
        # Arrange
        repo_path = "/tmp/test-app"
        branch_name = "fix-bug"
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        create_branch.run(f"{repo_path},{branch_name}")

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.checkout.assert_called_once_with("-b", branch_name)

    @patch("agent_src.tools.git_tool._get_repo")
    def test_commit(self, mock_get_repo):
        # Arrange
        repo_path = "/tmp/test-app"
        message = "Fixing a bug"
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        commit.run(f"{repo_path},{message}")

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.add.assert_called_once_with(A=True)
        mock_repo.git.commit.assert_called_once_with(m=message)

    @patch("agent_src.tools.git_tool._get_repo")
    def test_push(self, mock_get_repo):
        # Arrange
        repo_path = "/tmp/test-app"
        branch_name = "fix-bug"
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        push.run(f"{repo_path},{branch_name}")

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.push.assert_called_once_with(
            "--set-upstream", "--force", "origin", "--", branch_name
        )

    @patch.dict("os.environ", {"DAA_GIT_MODE": "api"}, clear=False)
    @patch("agent_src.tools.clonefree_client.CloneFreeGitClient")
    def test_create_pull_request(self, mock_client_cls):
        # Arrange
        repo_path = "/tmp/test-app"
        title = "Fix bug"
        description = "This PR fixes a bug"
        mock_client = MagicMock()
        mock_client.default_branch = "main"
        mock_client.create_pull_request.return_value = "http://example.com/pr/1"
        mock_client_cls.return_value = mock_client

        # Act
        result = create_pull_request.run(
            json.dumps(
                {"repo_path": repo_path, "title": title, "description": description}
            )
        )

        # Assert
        self.assertEqual(result, "http://example.com/pr/1")
        mock_client_cls.assert_called_once_with("test-app")
        mock_client.create_pull_request.assert_called_once_with(
            "main",
            title,
            description,
            base_branch="main",
        )


if __name__ == "__main__":
    unittest.main()
