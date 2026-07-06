const axios = require('axios');

class DaaSdk {
  constructor(options = {}) {
    this.backendUrl = options.backendUrl || process.env.DAA_BACKEND_API_URL || 'http://localhost:8000';
    this.token = options.token || process.env.DAA_TOKEN;
    this.appName = options.appName || process.env.REPO_NAME || 'default-node-app';
  }

  /**
   * Captures an exception, extracts stack trace and sends it to the DAA backend.
   * @param {Error} error - The JavaScript Error object to log.
   */
  async captureException(error) {
    const log = {
      content: JSON.stringify({
        message: error.message || String(error),
        stack_trace: error.stack || '',
        context: {},
        timestamp: new Date().toISOString()
      }),
      app_name: this.appName
    };
    return this.sendLog(log);
  }

  /**
   * Sends a structured log payload to the DAA backend.
   * @param {object} log - Log payload with content and app_name.
   */
  async sendLog(log) {
    try {
      const headers = {};
      if (this.token) {
        headers['Authorization'] = `Bearer ${this.token}`;
      }
      
      const response = await axios.post(`${this.backendUrl}/logs/`, log, { headers });
      return response.data;
    } catch (err) {
      console.error(`Failed to send log to DAA backend: ${err.message}`);
      if (err.response) {
        console.error(`Backend response: ${JSON.stringify(err.response.data)}`);
      }
    }
  }
}

module.exports = DaaSdk;
