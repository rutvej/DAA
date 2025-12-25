# Python Agent API Contract

## 1. `POST /analysis`

This endpoint is used to send the analysis report to the Daa backend API.

### Request Body

```json
{
    "log_id": "string",
    "status": "string",
    "pull_request_url": "string"
}
```

### Response Body

```json
{
    "status": "success"
}
```
