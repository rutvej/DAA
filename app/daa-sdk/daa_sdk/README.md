# DAA Python SDK

The Python SDK for DAA (Dynamic Application Analytics) allows you to capture exceptions and send logs to your DAA backend.

## Installation

```bash
pip install daa-sdk
```

## Usage

### Initialization

The `DaaSdk` constructor takes a single optional argument for the backend URL. The rest of the configuration is loaded from environment variables.

```python
from daa_sdk import DaaSdk

# backend_url is optional. If not provided, it defaults to the DAA_BACKEND_API_URL environment variable.
daa = DaaSdk(backend_url="http://localhost:8000")
```

### Capturing Exceptions

To capture an exception and send it to the DAA backend:

```python
try:
    # Your application logic here
    1 / 0
except Exception as e:
    # Pass the exception object directly
    daa.capture_exception(e)
```

### Sending Custom Logs

You can send custom logs using `send_log`:

```python
daa.send_log({
    "content": '{"message": "Custom event"}',
    "app_name": "my-python-app"
})
```

## Configuration

Configuration primarily relies on the following environment variables:
- `DAA_BACKEND_API_URL`: The URL of your DAA backend.
- `DAA_TOKEN`: Your authorization token.
- `REPO_NAME`: The name of your application/repository (defaults to `"default-app"` if not set).
