# DAA Node.js SDK

Easily integrate DAA (Developer Agentic Assistant) with Node.js applications to automatically capture errors and trigger agentic pull requests/postmortems.

## Installation

```bash
npm install axios
```

## Usage

```javascript
const DaaSdk = require('./daa-sdk');

const daa = new DaaSdk({
  backendUrl: 'http://localhost:8000',
  token: 'YOUR_DAA_TOKEN',
  appName: 'my-express-app'
});

// Express error handler integration
app.use((err, req, res, next) => {
  daa.captureException(err);
  res.status(500).send('Something broke!');
});
```
