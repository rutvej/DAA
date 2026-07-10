FROM python:3.11-alpine

# Install system dependencies
RUN apk add --no-cache git curl bash docker-cli

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY . .

# Setup default environment variables
ENV DAA_DB_PROVIDER=sqlite
ENV PORT=8080

EXPOSE 8080

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
