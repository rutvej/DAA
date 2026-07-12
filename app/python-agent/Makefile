PHONY: setup test lint format

setup:
	uv venv
	uv pip install -r requirements.txt

test:
	. .venv/bin/activate && PYTHONPATH=. python3 -m unittest discover tests

lint:
	. .venv/bin/activate && ruff check .

format:
	. .venv/bin/activate && ruff format .
