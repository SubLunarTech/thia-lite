// Thia-Lite Desktop App
// AI Astrology Assistant with local & cloud LLM support

const API_BASE = 'http://localhost:8765';

// ─── Logging ───────────────────────────────────────────────────────────────────

function log(level, ...args) {
    const timestamp = new Date().toISOString();
    const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
    console[level]?.(`[${timestamp}] ${message}`) || console.log(`[${timestamp}] [${level}] ${message}`);
}

function logError(...args) { log('error', ...args); }
function logWarn(...args) { log('warn', ...args); }
function logInfo(...args) { log('info', ...args); }
function logDebug(...args) { log('debug', ...args); }

window.addEventListener('error', (event) => {
    logError('Uncaught error:', event.message, event.filename, event.lineno);
});
window.addEventListener('unhandledrejection', (event) => {
    logError('Unhandled rejection:', event.reason);
});

// ─── Memories Modal ──────────────────────────────────────────────────────────

async function openMemories() {
    const modal = document.getElementById('memories-modal');
    if (modal) modal.classList.remove('hidden');

    const birthDataContainer = document.getElementById('memories-birth-data');
    const factsContainer = document.getElementById('memories-facts-list');

    if (birthDataContainer) birthDataContainer.innerHTML = 'Loading...';
    if (factsContainer) factsContainer.innerHTML = 'Loading...';

    if (window.electronAPI?.getMemories) {
        try {
            const mems = await window.electronAPI.getMemories();
            if (mems) {
                // Render birth data
                if (mems.birth_info) {
                    birthDataContainer.innerHTML = `
                        <div class="memory-item">
                            ${JSON.stringify(mems.birth_info, null, 2)}
                        </div>`;
                } else {
                    birthDataContainer.innerHTML = '<div class="memory-item">No birth data saved yet.</div>';
                }

                // Render facts
                if (mems.facts && Object.keys(mems.facts).length > 0) {
                    factsContainer.innerHTML = '';
                    for (const [key, value] of Object.entries(mems.facts)) {
                        factsContainer.innerHTML += `
                            <div class="memory-item">
                                <strong>${key}</strong>: ${value}
                            </div>`;
                    }
                } else {
                    factsContainer.innerHTML = '<div class="memory-item">No facts saved yet.</div>';
                }
            } else {
                birthDataContainer.innerHTML = 'Failed to load memories (Offline)';
                factsContainer.innerHTML = 'Failed to load memories (Offline)';
            }
        } catch (e) {
            logError('Error fetching memories:', e);
        }
    }
}

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
const apiKeyInput = document.getElementById('setting-api-key');
const localModelSelect = document.getElementById('setting-local-model');
let localModelsConfig = null;
const tempInput = document.getElementById('setting-temp');
const tempValue = document.getElementById('temp-value');

// ─── Initialization ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    logInfo('App initializing...');

    loadConversations();

    sendBtn?.addEventListener('click', sendMessage);
    const memoriesBtn = document.getElementById('memories-btn');
    const memoriesModal = document.getElementById('memories-modal');
    const closeMemoriesBtn = document.getElementById('close-memories-btn');

    newChatBtn?.addEventListener('click', newConversation);
    settingsBtn?.addEventListener('click', openSettings);

    memoriesBtn?.addEventListener('click', openMemories);
    closeMemoriesBtn?.addEventListener('click', () => {
        if (memoriesModal) memoriesModal.classList.add('hidden');
    });

    if (window.electronAPI?.onToolCall) {
        window.electronAPI.onToolCall((tc) => {
            appendToolCall(tc);
        });
    }

    inputBox?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    tempInput?.addEventListener('input', (e) => {
        if (tempValue) tempValue.textContent = e.target.value;
    });

    // Update model indicator with current LLM status
    await updateModelIndicator();

    logInfo('App initialized');
});

async function updateModelIndicator() {
    if (!modelIndicator || !window.electronAPI?.getLLMStatus) return;
    try {
        const status = await window.electronAPI.getLLMStatus();
        if (status.provider === 'local') {
            modelIndicator.textContent = 'Qwen 3.5 · Local';
        } else if (status.provider) {
            const names = { openai: 'OpenAI', anthropic: 'Anthropic', openrouter: 'OpenRouter' };
            modelIndicator.textContent = `${names[status.provider] || status.provider} · Cloud`;
        } else {
            modelIndicator.textContent = 'Not configured';
        }
    } catch {
        modelIndicator.textContent = 'Qwen 3.5 · Local';
    }
}

// ─── Chat ────────────────────────────────────────────────────────────────────

async function sendMessage() {
    const content = inputBox?.value?.trim();
    if (!content || isStreaming) return;

    logInfo('Sending message:', content);
    inputBox.value = '';
    isStreaming = true;

    if (welcomeScreen) welcomeScreen.style.display = 'none';
    appendMessage('user', content);

    const thinkingEl = appendMessage('assistant', '');
    thinkingEl.innerHTML = '<div class="thinking-dots"><span class="eso">☾</span><span class="eso">✦</span><span class="eso">☽</span></div>';

    try {
        currentConversation = await window.electronAPI.saveMessage(currentConversation, { role: 'user', content: content });
        const messages = await window.electronAPI.getMessages(currentConversation);

        const data = await window.electronAPI.chat(messages, {
            temperature: parseFloat(tempInput?.value || 0.3)
        });

        thinkingEl.remove();

        if (data.error) {
            appendMessage('assistant', `⚠️ **Error:** ${data.error}`);
        } else {
            const finalMsg = data.content || 'No response from the agent.';
            await window.electronAPI.saveMessage(currentConversation, { role: 'assistant', content: finalMsg });
            appendMessage('assistant', finalMsg);

            // Re-render to update conversation title
            loadConversations();
        }
    } catch (err) {
        logError('Chat error:', err);
        thinkingEl.remove();
        appendMessage('assistant', `⚠️ LLM Error: ${err.message}`);
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
    if (!tc) return;

    // Safely format arguments, handling both objects and strings
    let argsStr = '';
    if (tc.arguments) {
        if (typeof tc.arguments === 'string') {
            argsStr = tc.arguments;
        } else {
            try {
                argsStr = JSON.stringify(tc.arguments);
            } catch (e) {
                argsStr = '[Object]';
            }
        }
    }

    const html = `
        <div class="tool-call success">
            <span class="tool-icon">⚡</span>
            <span class="tool-name">${tc.name || 'tool'}</span>
            <span class="tool-args">${argsStr.slice(0, 100)}${argsStr.length > 100 ? '...' : ''}</span>
        </div>
    `;
    const container = document.getElementById('messages-container');
    if (container) {
        container.insertAdjacentHTML('beforeend', html);
        scrollToBottom();
    }
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
        if (window.electronAPI?.getConversations) {
            conversations = await window.electronAPI.getConversations();
            renderConversationList();
        }
    } catch (err) {
        logWarn('Failed to get conversations via IPC:', err.message);
    }
}

function renderConversationList() {
    if (!conversationList) return;
    conversationList.innerHTML = '';
    for (const conv of conversations) {
        const item = document.createElement('div');
        item.className = 'conv-item' + (conv.id === currentConversation ? ' active' : '');
        item.onclick = () => loadConversation(conv.id);

        const titleSpan = document.createElement('span');
        titleSpan.className = 'conversation-title';
        titleSpan.textContent = conv.title || 'New Chat';

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-conv-btn';
        deleteBtn.innerHTML = '🗑️';
        deleteBtn.title = 'Delete Conversation';

        deleteBtn.onclick = async (e) => {
            e.stopPropagation(); // prevent clicking the conversation body
            if (confirm(`Are you sure you want to delete "${conv.title || 'this chat'}"?`)) {
                if (window.electronAPI?.deleteConversation) {
                    await window.electronAPI.deleteConversation(conv.id);
                    await loadConversations();
                    // If we deleted the active chat, reset to welcome screen
                    if (currentConversation === conv.id) {
                        currentConversation = null;
                        document.getElementById('messages').innerHTML = '';
                        document.getElementById('welcome-screen')?.classList.remove('hidden');
                    }
                }
            }
        };

        item.appendChild(titleSpan);
        item.appendChild(deleteBtn);
        conversationList.appendChild(item);
    }
}

async function loadConversation(convId) {
    logInfo('Loading conversation:', convId);
    currentConversation = convId;
    try {
        if (window.electronAPI?.getMessages) {
            const messages = await window.electronAPI.getMessages(convId);
            chatMessages.innerHTML = '';
            if (welcomeScreen) welcomeScreen.style.display = 'none';
            for (const msg of messages) {
                appendMessage(msg.role, msg.content);
            }
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

async function loadSettings() {
    if (!localModelsConfig && window.electronAPI?.getLocalModelsConfig) {
        try {
            localModelsConfig = await window.electronAPI.getLocalModelsConfig();
            if (localModelSelect) {
                localModelSelect.innerHTML = '';
                for (const m of localModelsConfig.models) {
                    const option = document.createElement('option');
                    option.value = m.id;
                    let text = `${m.name} (${Math.round(m.sizeBytes / 1e8) / 10} GB)`;
                    if (m.id === localModelsConfig.recommendedId) {
                        text += ' — Recommended';
                    }
                    option.textContent = text;
                    localModelSelect.appendChild(option);
                }
            }
        } catch (e) {
            logError('Failed to load local models config', e);
        }
    }

    // Load from LLM status via IPC
    if (window.electronAPI?.getLLMStatus) {
        try {
            const status = await window.electronAPI.getLLMStatus();
            if (providerSelect && status.provider) {
                providerSelect.value = status.provider;
            }
            if (apiKeyInput && status.config?.apiKey) {
                apiKeyInput.value = status.config.apiKey;
            }
            if (localModelSelect && status.provider === 'local' && status.config?.modelId) {
                localModelSelect.value = status.config.modelId;
            } else if (localModelSelect && localModelsConfig) {
                localModelSelect.value = localModelsConfig.recommendedId;
            }
        } catch { }
    }

    const settings = JSON.parse(localStorage.getItem('thia-settings') || '{}');
    if (tempInput) {
        tempInput.value = settings.temperature || 0.3;
        if (tempValue) tempValue.textContent = settings.temperature || 0.3;
    }

    // Show/hide API key field based on provider
    toggleApiKeyVisibility();
    providerSelect?.addEventListener('change', toggleApiKeyVisibility);
}

function toggleApiKeyVisibility() {
    const provider = providerSelect?.value;
    const apiKeyGroup = document.getElementById('api-key-group');
    const localGroup = document.getElementById('local-group');
    if (apiKeyGroup) {
        apiKeyGroup.style.display = (provider === 'local') ? 'none' : 'block';
    }
    if (localGroup) {
        localGroup.style.display = (provider === 'local') ? 'block' : 'none';
    }
}

async function saveSettings() {
    const provider = providerSelect?.value || 'local';
    const apiKey = apiKeyInput?.value?.trim() || '';
    const temperature = parseFloat(tempInput?.value || 0.3);
    const modelId = localModelSelect?.value;

    // Save temperature locally
    localStorage.setItem('thia-settings', JSON.stringify({ temperature }));

    // Switch LLM provider via IPC
    if (window.electronAPI?.switchProvider) {
        try {
            await window.electronAPI.switchProvider(provider, { apiKey, modelId });
            logInfo('Provider switched to:', provider);
        } catch (e) {
            logError('Provider switch failed:', e);
        }
    }

    await updateModelIndicator();
    closeSettings();
}

function openSettings() {
    loadSettings();
    if (settingsModal) settingsModal.classList.remove('hidden');
}

function closeSettings() {
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
    const overlay = document.getElementById('chart-overlay');
    const display = document.getElementById('chart-display');
    if (overlay && display) {
        display.innerHTML = svg;
        overlay.classList.remove('hidden');
        // Make SVG responsive
        const svgEl = display.querySelector('svg');
        if (svgEl) {
            svgEl.setAttribute('width', '100%');
            svgEl.setAttribute('height', '100%');
            svgEl.style.maxWidth = '600px';
            svgEl.style.margin = '0 auto';
            svgEl.style.display = 'block';
        }
    }
}

function closeChart() {
    const overlay = document.getElementById('chart-overlay');
    if (overlay) overlay.classList.add('hidden');
}

// ─── Voice Input (Web Speech API) ────────────────────────────────────────────

let recognition = null;
let isListening = false;

function toggleVoice() {
    if (isListening) {
        stopVoice();
    } else {
        startVoice();
    }
}

function startVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        logWarn('Speech recognition not supported');
        appendMessage('assistant', 'Voice input is not supported in this environment. Try typing your question instead.');
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    const voiceBtn = document.getElementById('voice-btn');
    const inputBox = document.getElementById('message-input');

    recognition.onstart = () => {
        isListening = true;
        if (voiceBtn) {
            voiceBtn.classList.add('listening');
            voiceBtn.style.background = '#ef4444';
            voiceBtn.style.color = '#fff';
        }
        logInfo('Voice recognition started');
    };

    recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        if (inputBox) inputBox.value = transcript;

        // Auto-send on final result
        if (event.results[event.results.length - 1].isFinal) {
            logInfo('Voice final:', transcript);
            stopVoice();
            if (transcript.trim()) {
                sendMessage();
            }
        }
    };

    recognition.onerror = (event) => {
        logError('Voice error:', event.error);
        stopVoice();
        if (event.error === 'not-allowed') {
            appendMessage('assistant', 'Microphone access denied. Please allow microphone access in your system settings.');
        }
    };

    recognition.onend = () => {
        stopVoice();
    };

    recognition.start();
}

function stopVoice() {
    isListening = false;
    const voiceBtn = document.getElementById('voice-btn');
    if (voiceBtn) {
        voiceBtn.classList.remove('listening');
        voiceBtn.style.background = '';
        voiceBtn.style.color = '';
    }
    if (recognition) {
        try { recognition.stop(); } catch { }
        recognition = null;
    }
}

// ─── In-App Updates ──────────────────────────────────────────────────────────

async function checkForUpdates() {
    const label = document.getElementById('update-label');
    if (label) label.textContent = 'Checking...';

    try {
        const res = await fetch(`${API_BASE}/update/check`);
        const data = await res.json();

        // Update version display
        const versionInfo = document.getElementById('version-info');
        if (versionInfo && data.current) {
            versionInfo.textContent = `v${data.current}`;
        }

        if (data.available) {
            if (label) label.textContent = `Update to v${data.version}`;
            const btn = document.getElementById('update-btn');
            if (btn) {
                btn.style.background = 'var(--accent, #7c3aed)';
                btn.style.color = '#fff';
                btn.onclick = () => applyUpdate(data);
            }
        } else {
            if (label) label.textContent = 'Up to date ✓';
            setTimeout(() => {
                if (label) label.textContent = 'Check for Updates';
            }, 3000);
        }
    } catch (err) {
        logWarn('Update check failed:', err.message);
        if (label) label.textContent = 'Check for Updates';
    }
}

async function applyUpdate(updateInfo) {
    const label = document.getElementById('update-label');
    if (label) label.textContent = 'Updating...';

    try {
        const res = await fetch(`${API_BASE}/update/apply`, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            if (label) label.textContent = 'Restart to finish';
            appendMessage('assistant',
                `✨ Updated to v${updateInfo.version}! Please restart the app to use the new version.`
            );
        } else {
            if (label) label.textContent = 'Update failed';
            appendMessage('assistant', `Update failed: ${data.message}`);
        }
    } catch (err) {
        logError('Update apply failed:', err);
        if (label) label.textContent = 'Update failed';
    }
}

// Auto-check for updates on startup (non-blocking)
setTimeout(checkForUpdates, 5000);
