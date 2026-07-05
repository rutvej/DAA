import json
import logging
import os

from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from ..llm_config import get_llm


class GetInstructionsInput(BaseModel):
    data: str = Field(
        description="A JSON string containing `error_log` and `codebase`. "
        "Example: {\"error_log\": {...}, \"codebase\": {\"main.py\": \"...\"}}"
    )


@tool(args_schema=GetInstructionsInput)
def get_instructions(data: str) -> str:
    """Gets instructions from the LLM to fix the error.

    Args:
        data: A JSON string containing `error_log` and `codebase`.

    Returns:
        A set of instructions to fix the error.
    """
    try:
        input_data = json.loads(data)
    except json.JSONDecodeError:
        return "Error: Invalid JSON string. Expected `error_log` and `codebase`."

    error_log = input_data.get("error_log")
    codebase = input_data.get("codebase")

    if not isinstance(error_log, dict):
        return "Error: `error_log` must be a JSON object."
    if not isinstance(codebase, dict):
        return "Error: `codebase` must be a JSON object mapping file paths to file contents."

    llm = get_llm()
    prompt = f"""
    Here is an error log:
    {error_log}

    Here is the codebase:
    {codebase}

    Please provide a set of instructions to fix the error.
    The instructions should be a series of commands to the file system and git tools.
    For example:
    write_file('app/main.py', 'new content')
    commit('Fix bug')
    create_pull_request('Fix bug', 'This PR fixes a bug')
    """
    logging.info(f"Prompt: {prompt}")
    response = llm.invoke(prompt)
    return response.content
