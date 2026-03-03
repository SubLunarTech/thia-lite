// Thia-Lite Desktop App
// Claude Desktop clone with live chart, voice, and chat

const API_BASE = 'http://localhost:8765';

// ─── State ──────────────────────────────────────────────────────────────────

let currentConversation = null;
let conversations = [];
let isStreaming = false;
let liveChartInterval = null;
let isVoiceMode = false;
let recognition = null;

// ─── DOM Elements ────────────────────────────────────────────────────────────

const chatMessages = document.getElementById('chat-messages');
const inputBox = document.getElementById('input-box');
const sendBtn = document.getElementById('send-btn');
const voiceBtn = document.getElementById('voice-btn');
const newChatBtn = document.getElementById('new-chat');
const liveChartContainer = document.getElementById('live-chart');
const conversationList = document.getElementById('conversation-list');
const welcomeScreen = document.getElementById('welcome-screen');
const chartToggle = document.getElementById('chart-toggle');

// ─── Initialization ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadConversations();
    initVoice();
    startLiveChart();

    sendBtn?.addEventListener('click', sendMessage);
    voiceBtn?.addEventListener('click', toggleVoice);
    newChatBtn?.addEventListener('click', newConversation);
    chartToggle?.addEventListener('click', toggleLiveChart);

    inputBox?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// ─── Chat ────────────────────────────────────────────────────────────────────

async function sendMessage() {
    const content = inputBox?.value?.trim();
    if (!content || isStreaming) return;

    inputBox.value = '';
    isStreaming = true;

    // Hide welcome, show user message
    if (welcomeScreen) welcomeScreen.style.display = 'none';
    appendMessage('user', content);

    // Show thinking indicator
    const thinkingEl = appendMessage('assistant', '');
    thinkingEl.innerHTML = '<div class="thinking"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: content,
                conversation_id: currentConversation,
            }),
        });

        const data = await res.json();

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
        }

        // Refresh conversation list
        loadConversations();

    } catch (err) {
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
        const res = await fetch(`${API_BASE}/conversations`);
        conversations = await res.json();
        renderConversationList();
    } catch (err) {
        console.log('Backend not available');
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
        console.error(err);
    }
    renderConversationList();
}

function newConversation() {
    currentConversation = null;
    if (chatMessages) chatMessages.innerHTML = '';
    if (welcomeScreen) welcomeScreen.style.display = 'flex';
    renderConversationList();
}

// ─── Voice Interaction ───────────────────────────────────────────────────────

function initVoice() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        if (voiceBtn) voiceBtn.style.display = 'none';
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        if (inputBox) inputBox.value = transcript;

        // Auto-send when speech ends
        if (event.results[event.results.length - 1].isFinal) {
            setTimeout(() => {
                if (inputBox?.value?.trim()) sendMessage();
            }, 500);
        }
    };

    recognition.onerror = (event) => {
        console.error('Speech error:', event.error);
        stopVoice();
    };

    recognition.onend = () => {
        stopVoice();
    };
}

function toggleVoice() {
    if (isVoiceMode) {
        stopVoice();
    } else {
        startVoice();
    }
}

function startVoice() {
    if (!recognition) return;
    isVoiceMode = true;
    if (voiceBtn) {
        voiceBtn.classList.add('active');
        voiceBtn.textContent = '🔴';
    }
    recognition.start();
}

function stopVoice() {
    if (!recognition) return;
    isVoiceMode = false;
    if (voiceBtn) {
        voiceBtn.classList.remove('active');
        voiceBtn.textContent = '🎤';
    }
    try { recognition.stop(); } catch (e) { }
}

// Also speak responses (TTS)
function speak(text) {
    if (!('speechSynthesis' in window)) return;
    // Strip markdown
    const clean = text.replace(/[*_`#\[\]]/g, '').replace(/<[^>]+>/g, '');
    const utterance = new SpeechSynthesisUtterance(clean.substring(0, 500));
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    speechSynthesis.speak(utterance);
}

// ─── Live Chart ──────────────────────────────────────────────────────────────

function startLiveChart() {
    refreshLiveChart();
    liveChartInterval = setInterval(refreshLiveChart, 60000); // Every minute
}

async function refreshLiveChart() {
    if (!liveChartContainer) return;
    try {
        const res = await fetch(`${API_BASE}/live-chart`);
        const data = await res.json();
        if (data.svg) {
            liveChartContainer.innerHTML = data.svg;
        }
    } catch (err) {
        // Backend not available
        liveChartContainer.innerHTML = `
            <div style="text-align:center;color:#666;padding:40px;">
                <div style="font-size:48px;margin-bottom:12px;">✦</div>
                <div>Live chart updates when backend is running</div>
            </div>`;
    }
}

function toggleLiveChart() {
    if (!liveChartContainer) return;
    const isHidden = liveChartContainer.style.display === 'none';
    liveChartContainer.style.display = isHidden ? 'block' : 'none';
    if (chartToggle) chartToggle.textContent = isHidden ? '📉 Hide Chart' : '📊 Live Chart';
}

function showChart(svg) {
    if (!liveChartContainer) return;
    liveChartContainer.innerHTML = svg;
    liveChartContainer.style.display = 'block';
}
