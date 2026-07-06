# DAA Telemetry SDK Integration Skill Guide

This document provides instructions on how to install, configure, and integrate the DAA SRE Telemetry SDK into microservices written in Python, Node.js, Go, and Java.

---

## 🔑 1. Environment & Authentication Setup

When you register an application via the DAA CLI (`daa init`) or Dashboard, a secure `DAA_TOKEN` is automatically generated for it. 

Your application must configure the following environment variables:
```bash
DAA_LOGS_URL=http://<daa-backend-api-host>:8000/logs/
DAA_TOKEN=daa_token_abcdef123456...
```

---

## 💻 2. Multi-Language SDK Integrations

### Python (FastAPI / Flask)
Install requests dependency:
```bash
pip install requests
```

Integration wrapper:
```python
import os
import uuid
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

DAA_LOGS_URL = os.environ.get("DAA_LOGS_URL")
DAA_TOKEN = os.environ.get("DAA_TOKEN")

def report_to_daa(exception_type: str, content: str, trace_id: str):
    if not DAA_LOGS_URL or not DAA_TOKEN:
        return
    payload = {
        "app_name": "my-python-service",
        "content": content,
        "exception_type": exception_type,
        "trace_id": trace_id,
        "correlation_id": str(uuid.uuid4())
    }
    headers = {"Authorization": f"Bearer {DAA_TOKEN}"}
    try:
        requests.post(DAA_LOGS_URL, json=payload, headers=headers, timeout=2.0)
    except Exception as e:
        print(f"Failed to report to DAA: {e}")
```

---

### Node.js (Express)
Install axios dependency:
```bash
npm install axios
```

Express Middleware:
```javascript
const axios = require('axios');
const crypto = require('crypto');

const DAA_LOGS_URL = process.env.DAA_LOGS_URL;
const DAA_TOKEN = process.env.DAA_TOKEN;

async function reportToDaa(exceptionType, content, traceId) {
    if (!DAA_LOGS_URL || !DAA_TOKEN) return;
    const payload = {
        app_name: 'my-node-service',
        content: content,
        exception_type: exceptionType,
        trace_id: traceId,
        correlation_id: crypto.randomUUID()
    };
    try {
        await axios.post(DAA_LOGS_URL, payload, {
            headers: { 'Authorization': `Bearer ${DAA_TOKEN}` },
            timeout: 2000
        });
    } catch (err) {
        console.error('Failed to report to DAA:', err.message);
    }
}

// Express Error Handler Middleware
app.use((err, req, res, next) => {
    const traceId = req.headers['x-trace-id'] || crypto.randomBytes(8).toString('hex');
    reportToDaa(err.name || 'Error', err.stack || err.message, traceId);
    res.status(500).json({ error: 'Internal Server Error', trace_id: traceId });
});
```

---

### Go (Standard Net/HTTP)
Go logging helper:
```go
package telemetry

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"time"
)

var (
	daaLogsURL = os.Getenv("DAA_LOGS_URL")
	daaToken   = os.Getenv("DAA_TOKEN")
)

type DaaPayload struct {
	AppName       string `json:"app_name"`
	Content       string `json:"content"`
	ExceptionType string `json:"exception_type"`
	TraceID       string `json:"trace_id"`
	CorrelationID string `json:"correlation_id"`
}

func ReportToDaa(exceptionType, content, traceID, correlationID string) {
	if daaLogsURL == "" || daaToken == "" {
		return
	}
	payload := DaaPayload{
		AppName:       "my-go-service",
		Content:       content,
		ExceptionType: exceptionType,
		TraceID:       traceID,
		CorrelationID: correlationID,
	}
	body, _ := json.Marshal(payload)
	
	req, _ := http.NewRequest("POST", daaLogsURL, bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+daaToken)

	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Do(req)
	if err == nil {
		resp.Body.Close()
	}
}
```

---

### Java (Spring Boot)
Spring global exception interceptor:
```java
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;
import java.util.UUID;

@ControllerAdvice
public class GlobalExceptionHandler {

    private final String daaLogsUrl = System.getenv("DAA_LOGS_URL");
    private final String daaToken = System.getenv("DAA_TOKEN");
    private final RestTemplate restTemplate = new RestTemplate();

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Object> handleAllExceptions(Exception ex) {
        String traceId = UUID.randomUUID().toString();
        reportToDaa(ex.getClass().getSimpleName(), ex.getMessage(), traceId);
        return new ResponseEntity<>(ex.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
    }

    private void reportToDaa(String exceptionType, String content, String traceId) {
        if (daaLogsUrl == null || daaToken == null) return;

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + daaToken);

        DaaPayload payload = new DaaPayload("my-java-service", content, exceptionType, traceId);
        HttpEntity<DaaPayload> entity = new HttpEntity<>(payload, headers);

        try {
            restTemplate.postForEntity(daaLogsUrl, entity, String.class);
        } catch (Exception e) {
            System.err.println("Failed to report to DAA: " + e.getMessage());
        }
    }

    private static class DaaPayload {
        public String app_name;
        public String content;
        public String exception_type;
        public String trace_id;
        public String correlation_id = UUID.randomUUID().toString();

        public DaaPayload(String appName, String content, String exceptionType, String traceId) {
            this.app_name = appName;
            this.content = content;
            this.exception_type = exceptionType;
            this.trace_id = traceId;
        }
    }
}
```
