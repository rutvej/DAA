import unittest
import json
from unittest.mock import patch
from src.tools.llm_tool import get_instructions

class TestLlmTool(unittest.TestCase):

    @patch('src.tools.llm_tool.ChatGoogleGenerativeAI')
    def test_get_instructions(self, mock_chat_google):
        # Arrange
        error_log = 'division by zero'
        mock_llm = mock_chat_google.return_value
        mock_llm.invoke.return_value.content = 'Fix the division by zero error.'

        # Act
        instructions = get_instructions.run({
            'data': json.dumps({
                'error_log': {'message': error_log},
                'codebase': {'main.py': 'print("hello")'}
            })
        })

        # Assert
        self.assertEqual(instructions, 'Fix the division by zero error.')
        mock_chat_google.assert_called_once_with(model='gemini-2.5-flash', logger=unittest.mock.ANY)
        mock_llm.invoke.assert_called_once()

if __name__ == '__main__':
    unittest.main()
