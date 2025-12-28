import unittest
from unittest.mock import patch, mock_open
from src.tools.file_system_tool import read_file, write_file, list_files

class TestFileSystemTool(unittest.TestCase):

    @patch('src.tools.file_system_tool.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='file content')
    def test_read_file(self, mock_open_file, mock_exists):
        # Arrange
        file_path = '/tmp/test.txt'

        # Act
        content = read_file(file_path)

        # Assert
        self.assertEqual(content, 'file content')
        mock_open_file.assert_called_once_with(file_path, 'r')

    @patch('src.tools.file_system_tool.os.path.exists', return_value=False)
    def test_read_file_not_found(self, mock_exists):
        # Arrange
        file_path = '/tmp/test.txt'

        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            read_file(file_path)

    @patch('builtins.open', new_callable=mock_open)
    def test_write_file(self, mock_open_file):
        # Arrange
        file_path = '/tmp/test.txt'
        content = 'new content'

        # Act
        write_file(f'{file_path},{content}')

        # Assert
        mock_open_file.assert_called_once_with(file_path, 'w')
        mock_open_file().write.assert_called_once_with(content)

    @patch('src.tools.file_system_tool.os.path.exists', return_value=True)
    @patch('src.tools.file_system_tool.os.listdir', return_value=['file1.txt', 'file2.txt'])
    def test_list_files(self, mock_listdir, mock_exists):
        # Arrange
        path = '/tmp'

        # Act
        files = list_files(path)

        # Assert
        self.assertEqual(files, ['file1.txt', 'file2.txt'])
        mock_listdir.assert_called_once_with(path)

    @patch('src.tools.file_system_tool.os.path.exists', return_value=False)
    def test_list_files_not_found(self, mock_exists):
        # Arrange
        path = '/tmp'

        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            list_files(path)

if __name__ == '__main__':
    unittest.main()
