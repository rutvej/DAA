# DAA Ruby SDK

## Usage

```ruby
require 'daa'

client = Daa::Client.new

begin
  # your code
rescue => e
  client.capture_exception(e)
end
```
