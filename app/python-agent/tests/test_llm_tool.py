import json
import unittest
from unittest.mock import MagicMock, patch

from agent_src.tools.llm_tool import get_instructions


class TestLlmTool(unittest.TestCase):
    @patch("agent_src.tools.llm_tool.get_llm")
    def test_get_instructions(self, mock_get_llm):
        # Arrange
        error_log = "division by zero"
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm.invoke.return_value.content = "Fix the division by zero error."

        # Act
        instructions = get_instructions.run(
            json.dumps(
                {
                    "error_log": {"message": error_log},
                    "codebase": {"main.py": 'print("hello")'},
                }
            )
        )

        # Assert
        self.assertEqual(instructions, "Fix the division by zero error.")
        mock_get_llm.assert_called_once()
        mock_llm.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
