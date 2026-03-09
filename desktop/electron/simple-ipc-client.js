#!/usr/bin/env node
/**
 * Simple IPC Client for Thia-Lite Python Backend
 * =================================================
 * Replaces MCP client with direct JSON-RPC over stdio.
 *
 * Simpler than MCP:
 * - No Content-Length framing
 * - No protocol negotiation
 * - No initialization handshake
 * - Direct request/response
 *
 * Features:
 * - Auto-reconnect on process exit
 * - Request timeout handling
 * - Pending request tracking
 * - Simple promise-based API
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class SimpleIPCClient extends require('events').EventEmitter {
  constructor() {
    super();
    this.process = null;
    this.pendingRequests = new Map();
    this.requestId = 0;
    this.isReady = false;
    this.isStarting = false;
    this._stdoutBuffer = '';
    this._retryCount = 0;
    this._maxRetries = 3;

    // Bind methods
    this._handleStdout = this._handleStdout.bind(this);
    this._handleStderr = this._handleStderr.bind(this);
    this._handleExit = this._handleExit.bind(this);
    this._handleError = this._handleError.bind(this);
  }

  /**
   * Start the Python backend process.
   * @param {string} backendPath - Path to Python executable or script
   * @param {Object} options - Options {cwd, env}
   */
  async start(backendPath, options = {}) {
    if (this.isStarting) {
      this.log('Already starting...');
      return;
    }

    if (this.isReady) {
      this.log('Already ready');
      return;
    }

    this.isStarting = true;
    const cwd = options.cwd || process.resourcesPath || path.resolve(__dirname, '..', '..');
    const env = { ...process.env, PYTHONUNBUFFERED: '1', ...options.env };

    this.log(`Starting backend: ${backendPath}`);

    // Determine if it's a bundled executable or Python module
    const isBundled = backendPath.endsWith('.exe') || backendPath.endsWith('thia-lite');
    const args = isBundled ? ['serve', '--mode', 'ipc'] : ['-m', 'thia_lite.ipc_server'];

    // Spawn the process
    this.process = spawn(
      isBundled ? backendPath : (process.platform === 'win32' ? 'python.exe' : 'python3'),
      args,
      {
        cwd,
        env,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true
      }
    );

    // Set up event handlers
    this.process.stdout.on('data', this._handleStdout);
    this.process.stderr.on('data', this._handleStderr);
    this.process.on('exit', this._handleExit);
    this.process.on('error', this._handleError);

    // Wait for process to be ready
    await this._waitForReady();
    this.isStarting = false;

    this.log('Backend started successfully');
    this.emit('ready');
  }

  /**
   * Call a tool/function on the backend.
   * @param {string} toolName - Name of the tool to call
   * @param {Object} args - Arguments for the tool
   * @param {number} timeout - Timeout in milliseconds (default: 30000)
   */
  async call(toolName, args = {}, timeout = 30000) {
    if (!this.isReady) {
      throw new Error('IPC client not ready');
    }

    const id = ++this.requestId;
    const request = {
      jsonrpc: '2.0',
      id,
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: args
      }
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject, tool: toolName });

      // Send request
      try {
        this.process.stdin.write(JSON.stringify(request) + '\n');
      } catch (err) {
        this.pendingRequests.delete(id);
        reject(new Error(`Failed to send request: ${err.message}`));
        return;
      }

      // Set timeout
      const timer = setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error(`IPC timeout: ${toolName} (${timeout}ms)`));
        }
      }, timeout);

      // Store timer for cleanup
      const pending = this.pendingRequests.get(id);
      if (pending) {
        pending.timer = timer;
      }
    });
  }

  /**
   * List all available tools.
   */
  async listTools() {
    if (!this.isReady) {
      throw new Error('IPC client not ready');
    }

    const id = ++this.requestId;
    const request = {
      jsonrpc: '2.0',
      id,
      method: 'tools/list',
      params: {}
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });

      try {
        this.process.stdin.write(JSON.stringify(request) + '\n');
      } catch (err) {
        this.pendingRequests.delete(id);
        reject(new Error(`Failed to send request: ${err.message}`));
      }

      // Shorter timeout for list
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error('IPC timeout: tools/list'));
        }
      }, 5000);
    });
  }

  /**
   * Ping the backend to check if it's alive.
   */
  async ping() {
    if (!this.isReady) {
      throw new Error('IPC client not ready');
    }

    const id = ++this.requestId;
    const request = {
      jsonrpc: '2.0',
      id,
      method: 'ping',
      params: {}
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });

      try {
        this.process.stdin.write(JSON.stringify(request) + '\n');
      } catch (err) {
        this.pendingRequests.delete(id);
        reject(new Error(`Failed to send ping: ${err.message}`));
      }

      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error('IPC timeout: ping'));
        }
      }, 3000);
    });
  }

  /**
   * Stop the backend process.
   */
  stop() {
    this.log('Stopping backend...');

    // Clear all pending requests
    for (const [id, pending] of this.pendingRequests) {
      if (pending.timer) {
        clearTimeout(pending.timer);
      }
      pending.reject(new Error('Backend stopped'));
    }
    this.pendingRequests.clear();

    if (this.process) {
      this.process.kill();
      this.process = null;
    }

    this.isReady = false;
    this.isStarting = false;
    this._retryCount = 0;

    this.log('Backend stopped');
    this.emit('stopped');
  }

  /**
   * Handle stdout from the backend process.
   */
  _handleStdout(data) {
    const text = data.toString();
    this._stdoutBuffer += text;

    // Process complete lines
    const lines = this._stdoutBuffer.split('\n');
    this._stdoutBuffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const response = JSON.parse(line);
        this._handleResponse(response);
      } catch (err) {
        this.log(`Failed to parse response: ${err.message}`);
        this.log(`Response: ${line.substring(0, 200)}`);
      }
    }
  }

  /**
   * Handle stderr from the backend process.
   */
  _handleStderr(data) {
    const text = data.toString();
    // Log all stderr on Windows for debugging, elsewhere only errors
    const isError = text.includes('ERROR') || text.includes('error') || text.includes('Error') ||
                    text.includes('Exception') || text.includes('Traceback');
    if (process.platform === 'win32' || isError) {
      this.log(`Backend stderr: ${text.trim().substring(0, 500)}`);
    }
  }

  /**
   * Handle a JSON-RPC response.
   */
  _handleResponse(response) {
    const id = response.id;

    if (id == null) {
      // Notification (no response expected)
      return;
    }

    const pending = this.pendingRequests.get(id);
    if (!pending) {
      this.log(`Received response for unknown request: ${id}`);
      return;
    }

    // Clear timeout
    if (pending.timer) {
      clearTimeout(pending.timer);
    }

    this.pendingRequests.delete(id);

    if (response.error) {
      pending.reject(new Error(response.error.message || 'Unknown error'));
    } else {
      // Extract result content
      const result = response.result || {};
      if (result.isError) {
        pending.reject(new Error(result.content?.error || 'Tool execution failed'));
      } else {
        pending.resolve(result.content);
      }
    }
  }

  /**
   * Handle process exit.
   */
  _handleExit(code, signal) {
    this.log(`Backend exited: code=${code}, signal=${signal}`);
    this.isReady = false;
    this.emit('exit', { code, signal });

    // Auto-retry if it crashed early
    if (this._retryCount < this._maxRetries && code !== 0) {
      this._retryCount++;
      this.log(`Retrying... (${this._retryCount}/${this._maxRetries})`);
      // Note: actual retry would need to be initiated by caller
    }
  }

  /**
   * Handle process error.
   */
  _handleError(err) {
    this.log(`Backend error: ${err.message}`);
    this.isReady = false;
    this.emit('error', err);
  }

  /**
   * Wait for the backend to be ready.
   */
  async _waitForReady() {
    // Send a ping to verify the backend is responsive
    const maxWait = 15000; // 15 seconds (much shorter than MCP's timeout)
    const startTime = Date.now();

    while (Date.now() - startTime < maxWait) {
      try {
        await this.ping();
        this.isReady = true;
        return;
      } catch (err) {
        // Not ready yet, wait a bit
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }

    throw new Error('Backend failed to start within timeout');
  }

  /**
   * Logging helper.
   */
  log(message) {
    console.log(`[SimpleIPC] ${message}`);
  }
}

module.exports = SimpleIPCClient;
