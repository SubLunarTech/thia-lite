/**
 * Thia-Lite LLM Engine
 * ====================
 * Unified LLM inference with two backends:
 *  - Local: node-llama-cpp (in-process, no Ollama needed)
 *  - Cloud: Direct HTTP to OpenAI/Anthropic/OpenRouter APIs
 *
 * Users choose on first launch and can switch anytime.
 */

const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');
const os = require('os');
const { EventEmitter } = require('events');

// Lazy Electron import — allows module to load in non-Electron contexts for testing
let _app;
function getApp() {
    if (!_app) {
        try { _app = require('electron').app; } catch { _app = null; }
    }
    return _app;
}

function getUserDataDir() {
    const electronApp = getApp();
    if (electronApp) return electronApp.getPath('userData');
    return path.join(require('os').homedir(), '.thia-lite');
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MODELS_DIR = path.join(getUserDataDir(), 'models');
const CONFIG_PATH = path.join(getUserDataDir(), 'llm-config.json');

// Local GGUF models from HuggingFace
const LOCAL_MODELS = [
    {
        id: 'qwen3.5-1.8b',
        name: 'Qwen 3.5 1.8B',
        fileName: 'qwen3.5-1_8b-q4_k_m.gguf',
        url: 'https://huggingface.co/Qwen/Qwen3.5-1.8B-GGUF/resolve/main/qwen3.5-1_8b-q4_k_m.gguf',
        sizeBytes: 1_200_000_000, // ~1.2 GB
        minMemGb: 0,
        desc: 'Fastest. Best for older or basic computers (< 8GB RAM).'
    },
    {
        id: 'qwen3.5-4b',
        name: 'Qwen 3.5 4B',
        fileName: 'qwen3.5-4b-q4_k_m.gguf',
        url: 'https://huggingface.co/Qwen/Qwen3.5-4B-GGUF/resolve/main/qwen3.5-4b-q4_k_m.gguf',
        sizeBytes: 2_600_000_000, // ~2.6 GB
        minMemGb: 8,
        desc: 'Balanced. Best for most modern computers (8GB+ RAM).'
    },
    {
        id: 'qwen3.5-7b',
        name: 'Qwen 3.5 7B',
        fileName: 'qwen3.5-7b-q4_k_m.gguf',
        url: 'https://huggingface.co/Qwen/Qwen3.5-7B-GGUF/resolve/main/qwen3.5-7b-q4_k_m.gguf',
        sizeBytes: 4_400_000_000, // ~4.4 GB
        minMemGb: 14,
        desc: 'High quality. Best for powerful machines (16GB+ RAM).'
    },
    {
        id: 'qwen3.5-14b',
        name: 'Qwen 3.5 14B',
        fileName: 'qwen3.5-14b-q4_k_m.gguf',
        url: 'https://huggingface.co/Qwen/Qwen3.5-14B-GGUF/resolve/main/qwen3.5-14b-q4_k_m.gguf',
        sizeBytes: 8_600_000_000, // ~8.6 GB
        minMemGb: 22,
        desc: 'Highest quality. Best for pro workstations (24GB+ RAM).'
    }
];

function getRecommendedModelId() {
    const totalMemGb = os.totalmem() / (1024 * 1024 * 1024);
    let recommended = LOCAL_MODELS[0].id;
    for (const model of LOCAL_MODELS) {
        if (totalMemGb >= model.minMemGb) {
            recommended = model.id;
        }
    }
    return recommended;
}

// Cloud provider endpoints
const CLOUD_PROVIDERS = {
    openai: {
        name: 'OpenAI',
        baseUrl: 'https://api.openai.com/v1',
        defaultModel: 'gpt-4o-mini',
        maxTokens: 4096,
    },
    anthropic: {
        name: 'Anthropic',
        baseUrl: 'https://api.anthropic.com/v1',
        defaultModel: 'claude-3-5-sonnet-20241022',
        maxTokens: 4096,
    },
    openrouter: {
        name: 'OpenRouter',
        baseUrl: 'https://openrouter.ai/api/v1',
        defaultModel: 'anthropic/claude-3-haiku',
        maxTokens: 4096,
    },
};

// ─── Config Persistence ──────────────────────────────────────────────────────

function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_PATH)) {
            return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
        }
    } catch (e) {
        console.error('Failed to load LLM config:', e.message);
    }
    return null;
}

function saveConfig(config) {
    try {
        fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true });
        fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');
    } catch (e) {
        console.error('Failed to save LLM config:', e.message);
    }
}

// ─── LLM Engine ──────────────────────────────────────────────────────────────

class LLMEngine extends EventEmitter {
    constructor() {
        super();
        this._config = loadConfig();
        this._localModel = null;
        this._localSession = null;
        this._llamaInstance = null;
        this._ready = false;
        this._initializing = false;
    }

    /** Check if the engine has been set up (provider chosen) */
    get isConfigured() {
        return this._config !== null && this._config.provider !== undefined;
    }

    /** Check if the engine is ready to accept chat requests */
    get isReady() {
        return this._ready;
    }

    /** Get current provider type: 'local' | 'openai' | 'anthropic' | 'openrouter' */
    get provider() {
        return this._config?.provider || null;
    }

    /** Get current config (safe copy) */
    get config() {
        return this._config ? { ...this._config } : null;
    }

    // ── Setup ─────────────────────────────────────────────────────────────

    getLocalModelsConfig() {
        const recommendedId = getRecommendedModelId();
        const systemRamGb = Math.round(os.totalmem() / (1024 * 1024 * 1024));
        return {
            models: LOCAL_MODELS,
            recommendedId,
            systemRamGb
        };
    }

    /**
     * Configure for local inference.
     * Downloads model if not already cached, then loads it.
     * @param {string} [modelId] - Which local model to use
     */
    async setupLocal(modelId) {
        if (!modelId) modelId = getRecommendedModelId();
        const modelDef = LOCAL_MODELS.find(m => m.id === modelId) || LOCAL_MODELS[1];
        this._config = { provider: 'local', model: modelDef.name, modelId: modelDef.id };
        saveConfig(this._config);
        await this._initLocal();
    }

    /**
     * Configure for cloud provider.
     * @param {string} provider - 'openai' | 'anthropic' | 'openrouter'
     * @param {string} apiKey - API key for the provider
     * @param {string} [model] - Optional model override
     */
    async setupCloud(provider, apiKey, model) {
        if (!CLOUD_PROVIDERS[provider]) {
            throw new Error(`Unknown provider: ${provider}. Use: ${Object.keys(CLOUD_PROVIDERS).join(', ')}`);
        }
        this._config = {
            provider,
            apiKey,
            model: model || CLOUD_PROVIDERS[provider].defaultModel,
        };
        saveConfig(this._config);
        this._ready = true;
        this.emit('ready', { provider });
    }

    /**
     * Switch provider at runtime.
     */
    async switchProvider(provider, options = {}) {
        // Dispose local model if switching away
        if (this._localModel) {
            await this.dispose();
        }
        this._ready = false;

        if (provider === 'local') {
            await this.setupLocal(options.modelId);
        } else {
            await this.setupCloud(provider, options.apiKey, options.model);
        }
    }

    /**
     * Initialize engine based on saved config.
     * Called on app startup after first-time setup.
     */
    async initialize() {
        if (!this._config) return false;
        if (this._initializing) return false;
        this._initializing = true;

        try {
            if (this._config.provider === 'local') {
                await this._initLocal();
            } else {
                this._ready = true;
                this.emit('ready', { provider: this._config.provider });
            }
            return true;
        } catch (e) {
            this.emit('error', e);
            return false;
        } finally {
            this._initializing = false;
        }
    }

    // ── Chat ──────────────────────────────────────────────────────────────

    /**
     * Send a chat completion request.
     * @param {Array<{role: string, content: string}>} messages
     * @param {Object} [options]
     * @param {number} [options.temperature=0.3]
     * @returns {Promise<{role: string, content: string, tool_calls?: Array}>}
     */
    async chat(messages, options = {}) {
        if (!this._ready) {
            throw new Error('LLM engine not ready. Call initialize() or setup first.');
        }

        const provider = this._config.provider;
        let response;
        if (provider === 'local') {
            response = await this._chatLocal(messages, options);
        } else {
            response = await this._chatCloud(messages, options);
        }

        // Phase 6: Restore Auto-Memory Extraction
        // After the LLM replies to the user, we send both the user's latest prompt
        // and the assistant's response to the Python engine to natively extract
        // astrological entities (planets, signs) and birth data directly into the DB.
        if (this.mcpClient) {
            try {
                const lastUserMsg = messages[messages.length - 1]?.content || '';
                const assistantMsg = response.content || '';
                const combinedText = `${lastUserMsg}\n\n${assistantMsg}`;
                // Execute silently in background, do not await or block
                this.mcpClient.callTool('parse_message_memory', { text: combinedText })
                    .catch(e => console.error('Silent memory extraction failed:', e));
            } catch (e) {
                console.error('Silent memory extraction error:', e);
            }
        }

        return response;
    }

    // ── Local Inference (node-llama-cpp) ──────────────────────────────────

    async _initLocal() {
        const modelId = this._config.modelId || getRecommendedModelId();
        const modelDef = LOCAL_MODELS.find(m => m.id === modelId) || LOCAL_MODELS[1];
        const modelPath = path.join(MODELS_DIR, modelDef.fileName);

        // Download model if not cached
        if (!fs.existsSync(modelPath)) {
            await this._downloadModel(modelDef, modelPath);
        }

        this.emit('status', 'Loading AI model...');

        try {
            // Dynamic import for node-llama-cpp (ESM module)
            const { getLlama, LlamaChatSession } = await import('node-llama-cpp');

            this._llamaInstance = await getLlama();
            const model = await this._llamaInstance.loadModel({ modelPath });
            const context = await model.createContext();
            this._localSession = new LlamaChatSession({ contextSequence: context.getSequence() });
            this._localModel = model;
            this._ready = true;
            this.emit('ready', { provider: 'local', model: modelDef.name });
        } catch (e) {
            this.emit('error', new Error(`Failed to load local model: ${e.message}`));
            throw e;
        }
    }

    async _chatLocal(messages, options) {
        // Build the prompt from messages
        const systemPrompt = messages
            .filter(m => m.role === 'system')
            .map(m => m.content)
            .join('\n');

        const lastUserMsg = messages
            .filter(m => m.role === 'user')
            .pop();

        if (!lastUserMsg) {
            return { role: 'assistant', content: 'No user message provided.' };
        }

        const prompt = systemPrompt
            ? `${systemPrompt}\n\nUser: ${lastUserMsg.content}`
            : lastUserMsg.content;

        try {
            // Check for tool calls
            let functions = undefined;
            if (this.mcpClient && this.mcpClient.tools && this.mcpClient.tools.length > 0) {
                const { defineChatSessionFunction } = await import('node-llama-cpp');
                functions = {};
                for (const tool of this.mcpClient.tools) {
                    functions[tool.name] = defineChatSessionFunction({
                        description: tool.description,
                        params: tool.inputSchema,
                        handler: async (args) => {
                            this.emit('tool-call', { name: tool.name, arguments: args });
                            try {
                                const result = await this.mcpClient.callTool(tool.name, args);
                                return result?.content?.[0]?.text || JSON.stringify(result);
                            } catch (e) {
                                return `Error executing tool: ${e.message}`;
                            }
                        }
                    });
                }
            }

            const response = await this._localSession.prompt(prompt, {
                temperature: options.temperature || 0.3,
                maxTokens: options.maxTokens || 4096,
                functions
            });

            return {
                role: 'assistant',
                content: response,
                tool_calls: null,
                done: true,
            };
        } catch (e) {
            return {
                role: 'assistant',
                content: `Error during local inference: ${e.message}`,
                tool_calls: null,
                done: true,
            };
        }
    }

    // ── Cloud Inference ───────────────────────────────────────────────────

    async _chatCloud(messages, options) {
        const provider = this._config.provider;
        const providerConfig = CLOUD_PROVIDERS[provider];
        const apiKey = this._config.apiKey;
        const model = this._config.model || providerConfig.defaultModel;

        if (!apiKey) {
            return {
                role: 'assistant',
                content: `Missing API key for ${providerConfig.name}. Please configure it in Settings.`,
                tool_calls: null,
                done: true,
            };
        }

        try {
            if (provider === 'anthropic') {
                return await this._chatAnthropic(messages, model, apiKey, options);
            } else {
                // OpenAI-compatible (openai, openrouter)
                return await this._chatOpenAI(provider, messages, model, apiKey, options);
            }
        } catch (e) {
            return {
                role: 'assistant',
                content: `Error communicating with ${providerConfig.name}: ${e.message}`,
                tool_calls: null,
                done: true,
            };
        }
    }

    async _chatOpenAI(provider, messages, model, apiKey, options) {
        const providerConfig = CLOUD_PROVIDERS[provider];
        const url = new URL(`${providerConfig.baseUrl}/chat/completions`);

        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`,
        };

        if (provider === 'openrouter') {
            headers['HTTP-Referer'] = 'https://github.com/thia-libre/thia-lite';
            headers['X-Title'] = 'Thia-Lite';
        }

        // Map MCP tools to OpenAI format
        let tools = undefined;
        if (this.mcpClient && this.mcpClient.tools && this.mcpClient.tools.length > 0) {
            tools = this.mcpClient.tools.map(t => ({
                type: 'function',
                function: {
                    name: t.name,
                    description: t.description,
                    parameters: t.inputSchema
                }
            }));
        }

        let currentMessages = [...messages];
        let maxLoops = 5;
        let loops = 0;

        while (loops < maxLoops) {
            loops++;

            const payload = {
                model,
                messages: currentMessages,
                temperature: options.temperature || 0.3,
                max_tokens: providerConfig.maxTokens,
            };

            if (tools) {
                payload.tools = tools;
                payload.tool_choice = 'auto';
            }

            const data = await this._httpPost(url, headers, payload);
            const message = data.choices?.[0]?.message || {};

            if (!message.tool_calls || message.tool_calls.length === 0) {
                return {
                    role: message.role || 'assistant',
                    content: message.content || '',
                    tool_calls: null,
                    done: true,
                };
            }

            // Handle tool calls
            currentMessages.push(message);
            for (const call of message.tool_calls) {
                if (call.type !== 'function') continue;

                let args;
                try {
                    args = JSON.parse(call.function.arguments || '{}');
                } catch (e) {
                    args = {};
                }

                this.emit('tool-call', { name: call.function.name, arguments: args });

                let toolResult;
                try {
                    const res = await this.mcpClient.callTool(call.function.name, args);
                    toolResult = res?.content?.[0]?.text || JSON.stringify(res);
                } catch (e) {
                    toolResult = `Error executing tool: ${e.message}`;
                }

                currentMessages.push({
                    role: 'tool',
                    tool_call_id: call.id,
                    name: call.function.name,
                    content: toolResult
                });
            }
        }

        return {
            role: 'assistant',
            content: 'Finished executing tools but reached maximum iteration limit.',
            tool_calls: null,
            done: true
        };
    }

    async _chatAnthropic(messages, model, apiKey, options) {
        const url = new URL(`${CLOUD_PROVIDERS.anthropic.baseUrl}/messages`);

        // Extract system prompt
        let systemPrompt = '';
        let anthropicMsgs = [];
        for (const m of messages) {
            if (m.role === 'system') {
                systemPrompt += m.content + '\n';
            } else {
                anthropicMsgs.push(m);
            }
        }

        // Map MCP tools to Anthropic format
        let tools = undefined;
        if (this.mcpClient && this.mcpClient.tools && this.mcpClient.tools.length > 0) {
            tools = this.mcpClient.tools.map(t => ({
                name: t.name,
                description: t.description,
                input_schema: t.inputSchema
            }));
        }

        const headers = {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
        };

        let maxLoops = 5;
        let loops = 0;

        while (loops < maxLoops) {
            loops++;

            const payload = {
                model,
                messages: anthropicMsgs,
                max_tokens: CLOUD_PROVIDERS.anthropic.maxTokens,
                temperature: options.temperature || 0.3,
            };

            if (systemPrompt.trim()) {
                payload.system = systemPrompt.trim();
            }

            if (tools && tools.length > 0) {
                payload.tools = tools;
            }

            const data = await this._httpPost(url, headers, payload);

            // Anthropic sometimes returns API errors at the root level instead of returning content
            if (data.type === 'error') {
                throw new Error(data.error?.message || 'Unknown Anthropic error');
            }

            const toolUseBlocks = (data.content || []).filter(b => b.type === 'tool_use');
            const textBlocks = (data.content || []).filter(b => b.type === 'text');

            if (toolUseBlocks.length === 0) {
                return {
                    role: 'assistant',
                    content: textBlocks.map(b => b.text).join('\n'),
                    tool_calls: null,
                    done: true,
                };
            }

            // We have tools to call. Add the assistant's turn to messages to maintain state.
            anthropicMsgs.push({
                role: 'assistant',
                content: data.content // push the entire content array which contains text + tool_use blocks
            });

            const toolResultsMsgs = [];
            for (const call of toolUseBlocks) {
                this.emit('tool-call', { name: call.name, arguments: call.input });

                let toolResult;
                try {
                    const res = await this.mcpClient.callTool(call.name, call.input);
                    toolResult = res?.content?.[0]?.text || JSON.stringify(res);
                } catch (e) {
                    toolResult = `Error executing tool: ${e.message}`;
                }

                toolResultsMsgs.push({
                    type: 'tool_result',
                    tool_use_id: call.id,
                    content: toolResult
                });
            }

            // Provide tool results back as user
            anthropicMsgs.push({
                role: 'user',
                content: toolResultsMsgs
            });
        }

        return {
            role: 'assistant',
            content: 'Finished executing tools but reached maximum iteration limit.',
            tool_calls: null,
            done: true
        };
    }

    // ── Model Download ────────────────────────────────────────────────────

    async _downloadModel(modelDef, destPath) {
        fs.mkdirSync(path.dirname(destPath), { recursive: true });

        return new Promise((resolve, reject) => {
            this.emit('download-start', { name: modelDef.name, size: modelDef.sizeBytes });

            const download = (url, redirectCount = 0) => {
                if (redirectCount > 5) {
                    reject(new Error('Too many redirects'));
                    return;
                }

                const client = url.startsWith('https') ? https : http;
                const tmpPath = destPath + '.download';

                client.get(url, (response) => {
                    // Handle redirects
                    if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
                        download(response.headers.location, redirectCount + 1);
                        return;
                    }

                    if (response.statusCode !== 200) {
                        reject(new Error(`Download failed: HTTP ${response.statusCode}`));
                        return;
                    }

                    const totalBytes = parseInt(response.headers['content-length'], 10) || modelDef.sizeBytes;
                    let downloadedBytes = 0;
                    let lastEmitTime = 0;

                    const file = fs.createWriteStream(tmpPath);

                    response.on('data', (chunk) => {
                        downloadedBytes += chunk.length;

                        const now = Date.now();
                        // Throttle IPC events to prevent freezing UI
                        if (now - lastEmitTime > 100) {
                            const percent = Math.round((downloadedBytes / totalBytes) * 100);
                            const mbDown = Math.round(downloadedBytes / 1024 / 1024);
                            const mbTotal = Math.round(totalBytes / 1024 / 1024);
                            this.emit('download-progress', { percent, mbDown, mbTotal });
                            lastEmitTime = now;
                        }
                    });

                    response.pipe(file);

                    file.on('finish', () => {
                        file.close();
                        // Emit 100% just in case the last chunk was throttled
                        this.emit('download-progress', {
                            percent: 100,
                            mbDown: Math.round(totalBytes / 1024 / 1024),
                            mbTotal: Math.round(totalBytes / 1024 / 1024)
                        });
                        // Rename temp file to final
                        fs.renameSync(tmpPath, destPath);
                        this.emit('download-complete');
                        resolve();
                    });

                    file.on('error', (err) => {
                        fs.unlink(tmpPath, () => { });
                        reject(err);
                    });
                }).on('error', (err) => {
                    reject(err);
                });
            };

            download(modelDef.url);
        });
    }

    // ── HTTP Helper ───────────────────────────────────────────────────────

    _httpPost(url, headers, body) {
        return new Promise((resolve, reject) => {
            const urlObj = typeof url === 'string' ? new URL(url) : url;
            const payload = JSON.stringify(body);

            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
                path: urlObj.pathname + urlObj.search,
                method: 'POST',
                headers: {
                    ...headers,
                    'Content-Length': Buffer.byteLength(payload),
                },
                timeout: 120000,
            };

            const client = urlObj.protocol === 'https:' ? https : http;
            const req = client.request(options, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    try {
                        resolve(JSON.parse(data));
                    } catch (e) {
                        reject(new Error(`Invalid JSON response: ${data.slice(0, 200)}`));
                    }
                });
            });

            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });

            req.write(payload);
            req.end();
        });
    }

    // ── Cleanup ───────────────────────────────────────────────────────────

    async dispose() {
        this._ready = false;
        if (this._localSession) {
            this._localSession = null;
        }
        if (this._localModel) {
            this._localModel = null;
        }
        if (this._llamaInstance) {
            this._llamaInstance = null;
        }
    }
}

module.exports = { LLMEngine, CLOUD_PROVIDERS, LOCAL_MODELS };
