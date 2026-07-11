import unittest
import json
from unittest.mock import patch, mock_open
from agent_src.tools.file_system_tool import read_file, write_file, list_files


class TestFileSystemTool(unittest.TestCase):
    @patch("agent_src.tools.file_system_tool.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="file content")
    def test_read_file(self, mock_open_file, mock_exists):
        # Arrange
        file_path = "/tmp/test.txt"

        # Act
        content = read_file.run(file_path)

        # Assert
        self.assertEqual(content, "file content")

    @patch.dict(
        "os.environ",
        {"DAA_GIT_MODE": "api", "DAA_TARGET_APP": "payment-api"},
        clear=False,
    )
    @patch("agent_src.tools.clonefree_client.CloneFreeGitClient")
    def test_read_file_api_mode_uses_target_app(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.default_branch = "main"
        mock_client.get_file_content.return_value = "api file content"

        content = read_file.run("requirements.txt")

        self.assertEqual(content, "api file content")
        mock_client_cls.assert_called_once_with("payment-api")
        mock_client.get_file_content.assert_called_once_with(
            "requirements.txt", ref="main"
        )

    @patch("agent_src.tools.file_system_tool.os.path.exists", return_value=False)
    def test_read_file_not_found(self, mock_exists):
        # Arrange
        file_path = "/tmp/test.txt"

        # Act
        content = read_file.run(file_path)

        # Assert
        self.assertTrue(content.startswith("File not found"))

    @patch("agent_src.tools.file_system_tool.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_write_file(self, mock_open_file, mock_exists):
        # Arrange
        file_path = "/tmp/test.txt"
        content = "new content"
        data_input = json.dumps({"file_path": file_path, "content": content})

        # Act
        res = write_file.run(data_input)

        # Assert
        self.assertEqual(res, "File written successfully.")

    @patch("agent_src.tools.file_system_tool.os.path.exists", return_value=True)
    @patch(
        "agent_src.tools.file_system_tool.os.listdir",
        return_value=["file1.txt", "file2.txt"],
    )
    def test_list_files(self, mock_listdir, mock_exists):
        # Arrange
        path = "/tmp"

        # Act
        files = list_files.run(path)

        # Assert
        self.assertEqual(files, ["file1.txt", "file2.txt"])

    @patch("agent_src.tools.file_system_tool.os.path.exists", return_value=False)
    def test_list_files_not_found(self, mock_exists):
        # Arrange
        path = "/tmp"

        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            list_files.run(path)


if __name__ == "__main__":
    unittest.main()
