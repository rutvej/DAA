import logging
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict


@tool
def get_instructions(error_log: dict, codebase: Dict[str, str]) -> str:
    """Gets instructions from the LLM to fix the error.

    Args:
        error_log: The error log to fix.
        codebase: The codebase to fix the error in.

    Returns:
        A set of instructions to fix the error.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", logger=logging.getLogger(__name__))
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

