// Thia-Lite Desktop App
// Claude Desktop clone with live chart, voice, and chat

const API_BASE = 'http://localhost:8765';

// ─── Logging ───────────────────────────────────────────────────────────────────

const LOG_FILE = 'thia-lite-debug.log';

function log(level, ...args) {
    const timestamp = new Date().toISOString();
    const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
    const logLine = `[${timestamp}] [${level.toUpperCase()}] ${message}`;

    // Console log
    console[level] || console.log(logLine, ...args);

    // Try to write to file (via Tauri API if available)
    if (window.__TAURI__) {
        window.__TAURI__.fs.writeTextFile(LOG_FILE, logLine + '\n', { append: true })
            .catch(() => {}); // Silently fail if file writing doesn't work
    }
}

function logError(...args) { log('error', ...args); }
function logWarn(...args) { log('warn', ...args); }
function logInfo(...args) { log('info', ...args); }
function logDebug(...args) { log('debug', ...args); }

// Global error handler
window.addEventListener('error', (event) => {
    logError('Uncaught error:', event.message, event.filename, event.lineno, event.colno, event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    logError('Unhandled promise rejection:', event.reason);
});

// ─── State ──────────────────────────────────────────────────────────────────

let currentConversation = null;
let conversations = [];
let isStreaming = false;

// ─── DOM Elements ────────────────────────────────────────────────────────────

const chatMessages = document.getElementById('messages');
const inputBox = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const conversationList = document.getElementById('conversation-list');
const welcomeScreen = document.getElementById('welcome-screen');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const modelIndicator = document.getElementById('model-indicator');

// Settings Inputs
const providerSelect = document.getElementById('setting-provider');
const hostInput = document.getElementById('setting-ollama-host');
const modelSelect = document.getElementById('setting-model');
const tempInput = document.getElementById('setting-temp');
const tempValue = document.getElementById('temp-value');

// ─── Initialization ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    logInfo('App initializing...');

    // Check DOM elements
    const elements = {
        chatMessages, inputBox, sendBtn, newChatBtn, conversationList,
        welcomeScreen, settingsBtn, settingsModal, modelIndicator,
        providerSelect, hostInput, modelSelect, tempInput, tempValue
    };

    for (const [name, el] of Object.entries(elements)) {
        if (!el) {
            logWarn(`Missing element: ${name}`);
        } else {
            logDebug(`Found element: ${name}`);
        }
    }

    loadConversations();

    sendBtn?.addEventListener('click', sendMessage);
    newChatBtn?.addEventListener('click', newConversation);
    settingsBtn?.addEventListener('click', openSettings);

    inputBox?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Temperature slider
    tempInput?.addEventListener('input', (e) => {
        if (tempValue) tempValue.textContent = e.target.value;
    });

    // Load settings
    loadSettings();

    logInfo('App initialized successfully');
});

// ─── Chat ────────────────────────────────────────────────────────────────────

async function sendMessage() {
    const content = inputBox?.value?.trim();
    if (!content || isStreaming) return;

    logInfo('Sending message:', content);
    inputBox.value = '';
    isStreaming = true;

    // Hide welcome, show user message
    if (welcomeScreen) welcomeScreen.style.display = 'none';
    appendMessage('user', content);

    // Show thinking indicator
    const thinkingEl = appendMessage('assistant', '');
    thinkingEl.innerHTML = '<div class="thinking-dots"><span class="eso">☾</span><span class="eso">✦</span><span class="eso">☽</span></div>';

    try {
        logDebug('Fetching:', `${API_BASE}/chat`);
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: content,
                conversation_id: currentConversation,
            }),
        });

        logDebug('Response status:', res.status);
        const data = await res.json();
        logDebug('Response data:', data);

        // Remove thinking indicator
        thinkingEl.remove();

        // Show tool calls if any
        if (data.tool_calls_made?.length > 0) {
            for (const tc of data.tool_calls_made) {
                appendToolCall(tc);
            }
        }

        // Show response
        appendMessage('assistant', data.content || 'No response');

        // Check for SVG chart in response
        if (data.content?.includes('<svg') || data.svg) {
            const svg = data.svg || extractSVG(data.content);
            if (svg) showChart(svg);
        }

        // Update conversation ID
        if (data.conversation_id) {
            currentConversation = data.conversation_id;
            logDebug('Conversation ID:', currentConversation);
        }

        // Refresh conversation list
        loadConversations();

    } catch (err) {
        logError('Chat error:', err);
        thinkingEl.remove();
        appendMessage('assistant', `Error: ${err.message}. Is the Thia backend running on port 8765?`);
    }

    isStreaming = false;
}

function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '✦';

    const body = document.createElement('div');
    body.className = 'message-body';
    body.innerHTML = formatMarkdown(content);

    div.appendChild(avatar);
    div.appendChild(body);
    chatMessages?.appendChild(div);
    chatMessages?.scrollTo(0, chatMessages.scrollHeight);
    return div;
}

function appendToolCall(tc) {
    const div = document.createElement('div');
    div.className = 'tool-call';
    div.innerHTML = `
        <div class="tool-header">
            <span class="tool-icon">⚡</span>
            <span class="tool-name">${tc.tool || 'unknown'}</span>
            <span class="tool-status">✓</span>
        </div>
        <div class="tool-result">${tc.result_summary || ''}</div>
    `;
    chatMessages?.appendChild(div);
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code class="$1">$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

function extractSVG(text) {
    const match = text?.match(/<svg[\s\S]*?<\/svg>/);
    return match ? match[0] : null;
}

// ─── Conversations ───────────────────────────────────────────────────────────

async function loadConversations() {
    try {
        logDebug('Loading conversations...');
        const res = await fetch(`${API_BASE}/conversations`);
        conversations = await res.json();
        logDebug('Loaded conversations:', conversations.length);
        renderConversationList();
    } catch (err) {
        logWarn('Backend not available for conversations:', err.message);
    }
}

function renderConversationList() {
    if (!conversationList) return;
    conversationList.innerHTML = '';
    for (const conv of conversations) {
        const item = document.createElement('div');
        item.className = 'conv-item' + (conv.id === currentConversation ? ' active' : '');
        item.textContent = conv.title || 'New Chat';
        item.onclick = () => loadConversation(conv.id);
        conversationList.appendChild(item);
    }
}

async function loadConversation(convId) {
    logInfo('Loading conversation:', convId);
    currentConversation = convId;
    try {
        const res = await fetch(`${API_BASE}/conversations/${convId}/messages`);
        const messages = await res.json();
        chatMessages.innerHTML = '';
        if (welcomeScreen) welcomeScreen.style.display = 'none';
        for (const msg of messages) {
            appendMessage(msg.role, msg.content);
        }
    } catch (err) {
        logError('Failed to load conversation:', err);
    }
    renderConversationList();
}

function newConversation() {
    logInfo('New conversation');
    currentConversation = null;
    if (chatMessages) chatMessages.innerHTML = '';
    if (welcomeScreen) welcomeScreen.style.display = 'flex';
    renderConversationList();
}

// ─── Voice Interaction ───────────────────────────────────────────────────────

function initVoice() {
    // Not implemented in current UI
}

// ─── Settings ───────────────────────────────────────────────────────────────

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('thia-settings') || '{}');
    logDebug('Loading settings:', settings);
    if (providerSelect) providerSelect.value = settings.provider || 'ollama';
    if (hostInput) hostInput.value = settings.ollamaHost || 'http://localhost:11434';
    if (modelSelect) modelSelect.value = settings.model || 'qwen2.5:7b';
    if (tempInput) {
        tempInput.value = settings.temperature || 0.3;
        if (tempValue) tempValue.textContent = settings.temperature || 0.3;
    }
}

function saveSettings() {
    const settings = {
        provider: providerSelect?.value || 'ollama',
        ollamaHost: hostInput?.value || 'http://localhost:11434',
        model: modelSelect?.value || 'qwen2.5:7b',
        temperature: parseFloat(tempInput?.value || 0.3),
    };
    logInfo('Saving settings:', settings);
    localStorage.setItem('thia-settings', JSON.stringify(settings));
    closeSettings();
}

function openSettings() {
    logDebug('Opening settings');
    if (settingsModal) settingsModal.classList.remove('hidden');
}

function closeSettings() {
    logDebug('Closing settings');
    if (settingsModal) settingsModal.classList.add('hidden');
}

// ─── Suggestions ─────────────────────────────────────────────────────────────

function sendSuggestion(text) {
    logInfo('Sending suggestion:', text);
    if (inputBox) {
        inputBox.value = text;
        sendMessage();
    }
}

// ─── Chart Display ────────────────────────────────────────────────────────────

function showChart(svg) {
    logDebug('Showing chart');
    // Chart display not implemented in current UI
}
