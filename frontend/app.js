class UIManager {
    constructor() {
        // Elements
        this.btnJoin = document.getElementById('btn-join');
        this.btnLeave = document.getElementById('btn-leave');
        this.dot = document.getElementById('connection-dot');
        this.connText = document.getElementById('connection-text');
        this.chatHistory = document.getElementById('chat-history');
        this.chatPlaceholder = document.querySelector('.chat-placeholder');
        this.statusText = document.getElementById('status-text');
        this.spinner = document.getElementById('status-spinner');
        this.visualizer = document.getElementById('audio-visualizer');
        this.latencyEl = document.getElementById('metric-latency');
        this.languageEl = document.getElementById('metric-language');
        this.toastContainer = document.getElementById('toast-container');
        this.twilioOverlay = document.getElementById('twilio-overlay');
        this.transportIndicator = document.getElementById('transport-mode-indicator');
        this.mainContent = document.getElementById('livekit-main');
    }

    setTransportMode(mode) {
        if (mode === 'twilio') {
            this.twilioOverlay.classList.remove('hidden');
            this.transportIndicator.textContent = 'Twilio Mode';
        } else {
            this.twilioOverlay.classList.add('hidden');
            this.transportIndicator.textContent = 'LiveKit Mode';
        }
    }

    setConnectionState(state) {
        this.dot.className = 'dot';
        switch(state) {
            case 'disconnected':
                this.dot.classList.add('error');
                this.connText.textContent = 'Disconnected';
                this.btnJoin.disabled = false;
                this.btnLeave.disabled = true;
                this.setStatus('Ready to connect');
                break;
            case 'connecting':
                this.dot.classList.add('connecting');
                this.connText.textContent = 'Connecting...';
                this.btnJoin.disabled = true;
                this.btnLeave.disabled = true;
                break;
            case 'connected':
                this.dot.classList.add('connected');
                this.connText.textContent = 'Connected ✓';
                this.btnJoin.disabled = true;
                this.btnLeave.disabled = false;
                this.setStatus('Waiting for greeting...');
                break;
        }
    }

    setStatus(text, showSpinner = false, showVisualizer = false) {
        this.statusText.textContent = text;
        this.statusText.style.color = showSpinner ? 'var(--text-primary)' : 'var(--text-secondary)';
        
        if (showSpinner) this.spinner.classList.remove('hidden');
        else this.spinner.classList.add('hidden');

        if (showVisualizer) {
            this.visualizer.classList.remove('hidden');
            this.visualizer.classList.add('active');
        } else {
            this.visualizer.classList.add('hidden');
            this.visualizer.classList.remove('active');
        }
    }

    updateMetrics(latency, language) {
        if (latency !== undefined) {
            this.latencyEl.textContent = `${latency}ms`;
            if (latency > 1000) {
                this.latencyEl.className = 'metric-value bad';
            } else {
                this.latencyEl.className = 'metric-value good';
            }
        }
        if (language !== undefined) {
            this.languageEl.textContent = language;
        }
    }

    addMessage(sender, text, meta) {
        if (this.chatPlaceholder) {
            this.chatPlaceholder.style.display = 'none';
        }

        const msgDiv = document.createElement('div');
        msgDiv.className = `message message-${sender === 'You' ? 'user' : 'bot'}`;
        
        const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        let metaHtml = `<span>${time}</span>`;
        
        if (meta && meta.latency) {
            metaHtml += `<span>⏱ ${meta.latency}ms</span>`;
        }
        if (meta && meta.language) {
            metaHtml += `<span>🗣 ${meta.language}</span>`;
        }

        msgDiv.innerHTML = `
            <div class="message-header">
                <span class="message-sender">${sender}</span>
                <span class="message-meta">${metaHtml}</span>
            </div>
            <div class="message-content">${text}</div>
        `;

        this.chatHistory.appendChild(msgDiv);
        this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
    }

    showToast(message, type = 'error') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${message}</span>`;
        
        this.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
}


class VoicePipelineClient {
    constructor(ui) {
        this.ui = ui;
        this.ws = null;
        this.room = null;
        this.API_BASE = 'http://localhost:5000/api/livekit'; // Backend API
        this.WS_URL = 'ws://localhost:5000/ws/frontend'; // Backend WS
        
        this.bindEvents();
        this.checkConfig();
    }

    bindEvents() {
        this.ui.btnJoin.addEventListener('click', () => this.joinCall());
        this.ui.btnLeave.addEventListener('click', () => this.leaveCall());
    }

    async checkConfig() {
        try {
            // Initiate WebSocket connection on load
            this.connectWebSocket();
        } catch (e) {
            this.ui.showToast('Backend unavailable. Is the server running?');
        }
    }

    connectWebSocket() {
        if (this.ws) return;
        
        this.ws = new WebSocket(this.WS_URL);
        
        this.ws.onopen = () => {
            console.log('Control WebSocket connected');
            this.ui.setConnectionState('disconnected'); // enable join button
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleBackendEvent(data);
        };
        
        this.ws.onclose = () => {
            this.ws = null;
            setTimeout(() => this.connectWebSocket(), 3000); // Reconnect
        };
        
        this.ws.onerror = (e) => {
            console.error('WebSocket error:', e);
            this.ui.showToast('WebSocket connection error. Make sure backend is running.');
        };
    }

    handleBackendEvent(data) {
        console.log('Received event:', data);
        switch(data.event) {
            case 'transport_mode':
                this.ui.setTransportMode(data.mode);
                break;
            case 'greeting_started':
                this.ui.setStatus('Greeting playing...', false, true);
                break;
            case 'greeting_complete':
                this.ui.setStatus('Ready for input');
                break;
            case 'transcription_received':
                this.ui.addMessage('You', data.text, { 
                    latency: data.latency_ms,
                    language: data.language
                });
                this.ui.updateMetrics(undefined, data.language);
                this.ui.setStatus('Processing STT...', true, false);
                break;
            case 'llm_response_generating':
                this.ui.setStatus('Generating response...', true, false);
                break;
            case 'llm_response_complete':
                this.ui.addMessage('Bot', data.full_text, { latency: data.latency_ms });
                this.ui.setStatus('Preparing audio...', true, false);
                break;
            case 'tts_playing':
                this.ui.setStatus('Bot speaking...', false, true);
                this.ui.updateMetrics(data.total_latency_ms);
                break;
            case 'tts_complete':
                this.ui.setStatus('Ready for input');
                break;
            case 'error':
                this.ui.showToast(data.error_message || 'Pipeline Error', 'error');
                this.ui.setStatus('Error occurred');
                break;
        }
    }

    async joinCall() {
        this.ui.setConnectionState('connecting');
        try {
            // 1. Get Token from Backend
            const response = await fetch(`${this.API_BASE}/join`, { method: 'POST' });
            if (!response.ok) throw new Error('Failed to fetch LiveKit token. Ensure backend is running.');
            const data = await response.json();
            
            // 2. Connect to LiveKit Room using CDN SDK
            this.room = new LivekitClient.Room();
            
            this.room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                console.log("TRACK SUBSCRIBED! Kind:", track.kind);
                if (track.kind === LivekitClient.Track.Kind.Audio || track.kind === LivekitClient.Track.Kind.Video) {
                    const element = track.attach();
                    document.body.appendChild(element);
                    console.log("Audio element attached to body:", element);
                    // Explicitly try to play to catch auto-play errors
                    if (element.play) {
                        element.play()
                            .then(() => console.log("Audio playing successfully!"))
                            .catch(e => console.error("Autoplay blocked! Error:", e));
                    }
                }
            });

            this.room.on(LivekitClient.RoomEvent.Disconnected, () => {
                this.ui.setConnectionState('disconnected');
            });

            await this.room.connect(data.roomUrl, data.token);
            
            // Built-in LiveKit method to resume AudioContext (helps with browser autoplay policies)
            await this.room.startAudio().catch(e => console.warn("AudioContext error:", e));
            
            // 3. Enable local mic
            await this.room.localParticipant.enableCameraAndMicrophone();

            this.ui.setConnectionState('connected');

        } catch (error) {
            console.error(error);
            this.ui.showToast(error.message);
            this.ui.setConnectionState('disconnected');
        }
    }

    async leaveCall() {
        if (this.room) {
            await this.room.disconnect();
            this.room = null;
        }
        this.ui.setConnectionState('disconnected');
        this.ui.addMessage('System', 'Disconnected from call', {});
    }
}

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    const ui = new UIManager();
    window.app = new VoicePipelineClient(ui);
});
