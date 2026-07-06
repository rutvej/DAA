import unittest
import json
from unittest.mock import patch, mock_open
from src.tools.file_system_tool import read_file, write_file, list_files

class TestFileSystemTool(unittest.TestCase):

    @patch('src.tools.file_system_tool.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='file content')
    def test_read_file(self, mock_open_file, mock_exists):
        # Arrange
        file_path = '/tmp/test.txt'

        # Act
        content = read_file.run(file_path)

        # Assert
        self.assertEqual(content, 'file content')

    @patch('src.tools.file_system_tool.os.path.exists', return_value=False)
    def test_read_file_not_found(self, mock_exists):
        # Arrange
        file_path = '/tmp/test.txt'

        # Act
        content = read_file.run(file_path)

        # Assert
        self.assertTrue(content.startswith("File not found"))

    @patch('src.tools.file_system_tool.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_write_file(self, mock_open_file, mock_exists):
        # Arrange
        file_path = '/tmp/test.txt'
        content = 'new content'
        data_input = json.dumps({"file_path": file_path, "content": content})

        # Act
        res = write_file.run(data_input)

        # Assert
        self.assertEqual(res, "File written successfully.")

    @patch('src.tools.file_system_tool.os.path.exists', return_value=True)
    @patch('src.tools.file_system_tool.os.listdir', return_value=['file1.txt', 'file2.txt'])
    def test_list_files(self, mock_listdir, mock_exists):
        # Arrange
        path = '/tmp'

        # Act
        files = list_files.run(path)

        # Assert
        self.assertEqual(files, ['file1.txt', 'file2.txt'])

    @patch('src.tools.file_system_tool.os.path.exists', return_value=False)
    def test_list_files_not_found(self, mock_exists):
        # Arrange
        path = '/tmp'

        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            list_files.run(path)

if __name__ == '__main__':
    unittest.main()
