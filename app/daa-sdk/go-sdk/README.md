# DAA Go SDK

## Usage

```go
import "github.com/daa/daa-go-sdk"

client := daa.NewClient("", "", "my-go-service")

if err := runTask(); err != nil {
    client.CaptureException(err)
}
```
