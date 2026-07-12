import unittest
from unittest.mock import patch

from agent_src.llm_config import MockChatModel


class TestMockChatModel(unittest.TestCase):
    def test_mock_model_emits_react_tool_call_then_final_answer(self):
        with patch.dict("os.environ", {"DAA_POLICY_ENABLED": "false"}, clear=False):
            model = MockChatModel()

            first = model._generate([])
            second = model._generate([])

        self.assertIn("Action: read_file", first.generations[0].message.content)
        self.assertIn("Final Answer:", second.generations[0].message.content)
        self.assertIn("WRITE_DIFF:", second.generations[0].message.content)

    def test_mock_model_policy_mode_emits_escalation_block(self):
        with patch.dict("os.environ", {"DAA_POLICY_ENABLED": "true"}, clear=False):
            model = MockChatModel()

            model._generate([])
            second = model._generate([])

        self.assertIn("Final Answer:", second.generations[0].message.content)
        self.assertIn("WRITE_ESCALATION:", second.generations[0].message.content)


if __name__ == "__main__":
    unittest.main()
