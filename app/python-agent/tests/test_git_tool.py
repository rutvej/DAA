import unittest
import json
from unittest.mock import patch, MagicMock
from src.tools.git_tool import clone_repo, create_branch, commit, push, create_pull_request

class TestGitTool(unittest.TestCase):

    def setUp(self):
        import os
        self.old_env = dict(os.environ)
        os.environ['GITLAB_USER'] = 'root'
        os.environ['GITLAB_HOST'] = 'gitlab'
        if 'GITLAB_PRIVATE_TOKEN' in os.environ:
            del os.environ['GITLAB_PRIVATE_TOKEN']

    def tearDown(self):
        import os
        os.environ.clear()
        os.environ.update(self.old_env)

    @patch('src.tools.git_tool.os.path.exists', return_value=False)
    @patch('src.tools.git_tool.git.Repo')
    def test_clone_repo(self, mock_repo, mock_exists):
        # Arrange
        app_name = 'test-app'
        expected_path = f"/tmp/{app_name}"
        mock_repo_instance = MagicMock()
        mock_repo.clone_from.return_value = mock_repo_instance

        # Act
        result = clone_repo.run(app_name)

        # Assert
        self.assertEqual(result, expected_path)
        mock_repo.clone_from.assert_called_once_with("http://root:None@gitlab:80/root/test-app.git", expected_path)
        mock_repo_instance.config_writer.assert_called_once()

    @patch('src.tools.git_tool.os.path.exists', return_value=True)
    @patch('src.tools.git_tool._get_repo')
    def test_clone_repo_updates_existing_remote(self, mock_get_repo, mock_exists):
        app_name = 'test-app'
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        result = clone_repo.run(app_name)

        self.assertEqual(result, f"/tmp/{app_name}")
        mock_get_repo.assert_called_once_with(f"/tmp/{app_name}")
        mock_repo.remotes.origin.set_url.assert_called_once_with(
            "http://root:None@gitlab:80/root/test-app.git"
        )

    @patch('src.tools.git_tool._get_repo')
    def test_create_branch(self, mock_get_repo):
        # Arrange
        repo_path = '/tmp/test-app'
        branch_name = 'fix-bug'
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        create_branch.run(f'{repo_path},{branch_name}')

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.checkout.assert_called_once_with('-b', branch_name)

    @patch('src.tools.git_tool._get_repo')
    def test_commit(self, mock_get_repo):
        # Arrange
        repo_path = '/tmp/test-app'
        message = 'Fixing a bug'
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        commit.run(f'{repo_path},{message}')

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.add.assert_called_once_with(A=True)
        mock_repo.git.commit.assert_called_once_with(m=message)

    @patch('src.tools.git_tool._get_repo')
    def test_push(self, mock_get_repo):
        # Arrange
        repo_path = '/tmp/test-app'
        branch_name = 'fix-bug'
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Act
        push.run(f'{repo_path},{branch_name}')

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_repo.git.push.assert_called_once_with('--set-upstream', '--force', 'origin', branch_name)

    @patch('src.tools.git_tool.gitlab.Gitlab')
    @patch('src.tools.git_tool._get_repo')
    def test_create_pull_request(self, mock_get_repo, mock_gitlab):
        # Arrange
        repo_path = '/tmp/test-app'
        title = 'Fix bug'
        description = 'This PR fixes a bug'
        mock_repo = MagicMock()
        mock_repo.active_branch.name = 'fix-bug'
        mock_repo.working_dir.split.return_value = ['/', 'tmp', 'test-app']
        mock_get_repo.return_value = mock_repo
        mock_gl = MagicMock()
        mock_gitlab.return_value = mock_gl
        mock_project = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        mock_project.mergerequests.list.return_value = [] # Fix MagicMock truthiness

        # Act
        create_pull_request.run(json.dumps({'repo_path': repo_path, 'title': title, 'description': description}))

        # Assert
        mock_get_repo.assert_called_once_with(repo_path)
        mock_gitlab.assert_called_once_with('http://gitlab', private_token=None)
        mock_gl.projects.get.assert_called_once_with('root/test-app')
        mock_project.mergerequests.create.assert_called_once_with({
            'source_branch': 'fix-bug',
            'target_branch': 'master',
            'title': title,
            'description': description
        })

if __name__ == '__main__':
    unittest.main()
