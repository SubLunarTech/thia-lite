const { EventEmitter } = require('events');

class MCPClient extends EventEmitter {
    constructor(process) {
        super();
        this.process = process;
        this.requestId = 1;
        this.pendingRequests = new Map();
        this.buffer = '';
        this.tools = [];
        this.initialized = false;

        this.process.stdout.on('data', this.handleData.bind(this));
    }

    handleData(data) {
        this.buffer += data.toString('utf8');
        this.processBuffer();
    }

    processBuffer() {
        while (true) {
            const match = this.buffer.match(/Content-Length: (\d+)\r\n\r\n/);
            if (!match) break;

            const headerLength = match[0].length;
            const contentLength = parseInt(match[1], 10);

            if (this.buffer.length < headerLength + contentLength) {
                // Not enough data yet
                break;
            }

            const messageStr = this.buffer.slice(headerLength, headerLength + contentLength);
            this.buffer = this.buffer.slice(headerLength + contentLength);

            try {
                const message = JSON.parse(messageStr);
                this.handleMessage(message);
            } catch (e) {
                this.emit('error', new Error(`Failed to parse MCP message: ${e.message}`));
            }
        }
    }

    handleMessage(message) {
        if (message.id !== undefined && this.pendingRequests.has(message.id)) {
            const { resolve, reject } = this.pendingRequests.get(message.id);
            this.pendingRequests.delete(message.id);

            if (message.error) {
                reject(new Error(message.error.message || 'Unknown MCP error'));
            } else {
                resolve(message.result);
            }
        } else if (message.method) {
            // Handle incoming notifications/requests from server if any
            this.emit('notification', message);
        }
    }

    async sendRequest(method, params = {}) {
        return new Promise((resolve, reject) => {
            const id = this.requestId++;
            const message = {
                jsonrpc: '2.0',
                id,
                method,
                params
            };

            this.pendingRequests.set(id, { resolve, reject });
            this._write(message);
        });
    }

    sendNotification(method, params = {}) {
        const message = {
            jsonrpc: '2.0',
            method,
            params
        };
        this._write(message);
    }

    _write(message) {
        if (!this.process || !this.process.stdin || this.process.stdin.destroyed) {
            this.emit('error', new Error('Cannot write to closed process'));
            return;
        }

        const messageStr = JSON.stringify(message);
        const lspPayload = `Content-Length: ${Buffer.byteLength(messageStr, 'utf8')}\r\n\r\n${messageStr}`;
        this.process.stdin.write(lspPayload);
    }

    async initialize() {
        if (this.initialized) return;

        const initResult = await this.sendRequest('initialize', {
            protocolVersion: '2024-11-05',
            capabilities: {},
            clientInfo: {
                name: 'thia-electron-client',
                version: '1.0.0'
            }
        });

        this.sendNotification('notifications/initialized');
        this.initialized = true;

        // Fetch tools
        const toolsResult = await this.sendRequest('tools/list');
        this.tools = toolsResult.tools || [];
        this.emit('ready', this.tools);
    }

    async callTool(name, arguments_ = {}) {
        if (!this.initialized) throw new Error('MCP Client not initialized');

        const result = await this.sendRequest('tools/call', {
            name,
            arguments: arguments_
        });

        return result;
    }
}

module.exports = { MCPClient };
