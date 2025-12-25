# Python Agent Data Model

## 1. Pydantic Models

The Python Agent uses Pydantic models to define the inputs and outputs of the tools. This ensures that the data is consistent and valid.

### 1.1. GitToolInput

```python
from pydantic import BaseModel

class GitToolInput(BaseModel):
    app_name: str
```

### 1.2. FileSystemToolInput

```python
from pydantic import BaseModel
from typing import Optional

class FileSystemToolInput(BaseModel):
    file_path: str
    content: Optional[str] = None
```

### 1.3. LLMToolInput

```python
from pydantic import BaseModel
from typing import Dict

class LLMToolInput(BaseModel):
    error_log: dict
    codebase: Dict[str, str]
```

### 1.4. DatabaseToolInput

```python
from pydantic import BaseModel
from typing import Optional

class DatabaseToolInput(BaseModel):
    log_id: str
    status: Optional[str] = None
    pull_request_url: Optional[str] = None
```

### 1.5. ErrorLog

```python
from pydantic import BaseModel

class ErrorLog(BaseModel):
    id: str
    message: str
    stack_trace: str
    context: dict
    timestamp: str
    app_name: str
```
