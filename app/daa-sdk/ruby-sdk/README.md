# DAA Ruby SDK

The Ruby SDK for DAA (Dynamic Application Analytics) allows you to capture exceptions and send logs to your DAA backend.

## Installation

Add this line to your application's Gemfile:

```ruby
gem 'daa'
```

## Usage

### Initialization

The `Daa::Client` initializer accepts keyword arguments:

```ruby
require 'daa'

daa = Daa::Client.new(
  backend_url: 'http://localhost:8000', # Optional. Defaults to ENV['DAA_BACKEND_API_URL'] or 'http://localhost:8000'
  token: 'your-auth-token',             # Optional. Defaults to ENV['DAA_TOKEN']
  app_name: 'my-ruby-app'               # Optional. Defaults to ENV['REPO_NAME'] or 'default-ruby-app'
)
```

### Capturing Exceptions

To capture an exception and send its stack trace:

```ruby
begin
  # Your application logic here
  raise "Something went wrong!"
rescue => e
  # Pass the exception object
  daa.capture_exception(e)
end
```

### Sending Custom Logs

Send a custom payload using `send_log`:

```ruby
daa.send_log({
  content: '{"message": "Custom log event"}',
  app_name: 'my-ruby-app'
})
```

## Configuration

You can also use environment variables for configuration:
- `DAA_BACKEND_API_URL`: The URL of your DAA backend (default: `http://localhost:8000`)
- `DAA_TOKEN`: Your authorization token
- `REPO_NAME`: The name of your application/repository (default: `default-ruby-app`)
