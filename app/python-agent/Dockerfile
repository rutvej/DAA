FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git golang-go && rm -rf /var/lib/apt/lists/*
COPY . .

RUN pip install -r requirements.txt

ENV PYTHONPATH="${PYTHONPATH}:/app"

CMD ["python", "-u", "-m", "src.main"]
