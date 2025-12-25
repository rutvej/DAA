# Daa SDK API Contract

## 1. `POST /logs`

This endpoint is used to send error logs to the Daa backend API.

### Request Body

```json
{
    "message": "string",
    "stack_trace": "string",
    "context": {
        "key": "value"
    },
    "timestamp": "string",
    "token": "string",
    "repo_name": "string"
}
```

### Response Body

```json
{
    "status": "success"
}
```
