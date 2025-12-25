.PHONY: setup test

setup:
	uv venv
	uv pip install -r requirements.txt

test:
	. .venv/bin/activate && python3 -m unittest discover tests
