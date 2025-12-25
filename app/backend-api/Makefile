.PHONY: test install

install:
	uv pip install -r app/backend-api/requirements.txt

test:
	DATABASE_URL=sqlite:///./test.db RABBITMQ_HOST=localhost PYTHONPATH=app/backend-api/src uv run pytest app/backend-api/tests/
