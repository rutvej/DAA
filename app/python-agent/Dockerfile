FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git
COPY . .

RUN pip install -r requirements.txt

CMD ["python", "-u", "src/main.py"]
