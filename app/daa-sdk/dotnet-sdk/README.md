# DAA .NET SDK

## Usage

```csharp
using Daa;

var client = new DaaClient();

try
{
    // your code
}
catch (Exception ex)
{
    await client.CaptureExceptionAsync(ex);
}
```
