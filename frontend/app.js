class UIManager {
    constructor() {
        // Elements
        this.btnJoin = document.getElementById('btn-join');
        this.btnLeave = document.getElementById('btn-leave');
        this.btnCallPhone = document.getElementById('btn-call-phone');
        this.phoneInput = document.getElementById('phone-input');
        this.callingModeSelect = document.getElementById('calling-mode-select');
        this.phoneInputContainer = document.getElementById('phone-input-container');
        this.dot = document.getElementById('connection-dot');
        this.connText = document.getElementById('connection-text');
        this.chatHistory = document.getElementById('chat-history');
        this.chatPlaceholder = document.querySelector('.chat-placeholder');
        this.statusText = document.getElementById('status-text');
        this.spinner = document.getElementById('status-spinner');
        this.visualizer = document.getElementById('audio-visualizer');
        this.latencyEl = document.getElementById('metric-latency');
        this.languageEl = document.getElementById('metric-language');
        this.emotionEl = document.getElementById('metric-emotion');
        this.toastContainer = document.getElementById('toast-container');
        this.twilioOverlay = document.getElementById('twilio-overlay');
        this.transportIndicator = document.getElementById('transport-mode-indicator');
        this.mainContent = document.getElementById('livekit-main');
        
        // Auth overlay elements
        this.authOverlay = document.getElementById('auth-overlay');
        this.btnLogin = document.getElementById('btn-login');
        this.authUsername = document.getElementById('auth-username');
        this.authPassword = document.getElementById('auth-password');
        this.authToggleLink = document.getElementById('auth-toggle-link');
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
                if (this.btnCallPhone) this.btnCallPhone.disabled = false;
                if (this.phoneInput) this.phoneInput.disabled = false;
                if (this.callingModeSelect) this.callingModeSelect.disabled = false;
                this.setStatus('Ready to connect');
                break;
            case 'connecting':
                this.dot.classList.add('connecting');
                this.connText.textContent = 'Connecting...';
                this.btnJoin.disabled = true;
                this.btnLeave.disabled = true;
                if (this.btnCallPhone) this.btnCallPhone.disabled = true;
                if (this.phoneInput) this.phoneInput.disabled = true;
                if (this.callingModeSelect) this.callingModeSelect.disabled = true;
                break;
            case 'connected':
                this.dot.classList.add('connected');
                this.connText.textContent = 'Connected ✓';
                this.btnJoin.disabled = true;
                this.btnLeave.disabled = false;
                if (this.btnCallPhone) this.btnCallPhone.disabled = true;
                if (this.phoneInput) this.phoneInput.disabled = true;
                if (this.callingModeSelect) this.callingModeSelect.disabled = true;
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

    updateMetrics(latency, language, emotion) {
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
        if (emotion !== undefined && this.emotionEl) {
            const emojiMap = { 'Happy': '😊', 'Frustrated': '😠', 'Confused': '🤔', 'Neutral': '😐' };
            const displayEmotion = emojiMap[emotion] ? `${emotion} ${emojiMap[emotion]}` : emotion;
            this.emotionEl.textContent = displayEmotion;
            const emotionClass = emotion.split(' ')[0].toLowerCase();
            this.emotionEl.className = `metric-value ${emotionClass}`;
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
        if (meta && meta.emotion) {
            const emojiMap = { 'Happy': '😊', 'Frustrated': '😠', 'Confused': '🤔', 'Neutral': '😐' };
            const displayEmotion = emojiMap[meta.emotion] ? `${meta.emotion} ${emojiMap[meta.emotion]}` : meta.emotion;
            metaHtml += `<span>🎭 ${displayEmotion}</span>`;
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
        this.API_BASE = '/api/livekit'; // Backend API (Relative path)
        
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.WS_URL = `${wsProtocol}//${window.location.host}/ws/frontend`; // Backend WS (Dynamic)
        
        // Auth token initialization
        this.token = localStorage.getItem('jwt_token') || '';
        this.isRegisterMode = false;
        
        this.bindEvents();
        this.checkConfig();
        
        // Sync calling mode on initial load
        if (this.ui.callingModeSelect) {
            this.handleCallingModeChange(this.ui.callingModeSelect.value);
        }
        
        // Check if admin is authenticated
        this.checkAuth();
    }

    bindEvents() {
        this.ui.btnJoin.addEventListener('click', () => this.joinCall());
        this.ui.btnLeave.addEventListener('click', () => this.leaveCall());
        if (this.ui.btnCallPhone) {
            this.ui.btnCallPhone.addEventListener('click', () => this.callPhone());
        }
        if (this.ui.callingModeSelect) {
            this.ui.callingModeSelect.addEventListener('change', (e) => this.handleCallingModeChange(e.target.value));
        }
        if (this.ui.btnLogin) {
            this.ui.btnLogin.addEventListener('click', () => this.handleLogin());
        }
        if (this.ui.authToggleLink) {
            this.ui.authToggleLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleAuthMode();
            });
        }
    }

    checkAuth() {
        if (!this.token) {
            if (this.ui.authOverlay) {
                this.ui.authOverlay.classList.remove('hidden');
            }
        } else {
            if (this.ui.authOverlay) {
                this.ui.authOverlay.classList.add('hidden');
            }
        }
    }

    toggleAuthMode() {
        this.isRegisterMode = !this.isRegisterMode;
        const card = this.ui.authOverlay.querySelector('.auth-card');
        const title = card.querySelector('h2');
        const subtitle = card.querySelector('.auth-subtitle');
        const submitBtn = this.ui.btnLogin;
        const toggleLink = this.ui.authToggleLink;

        if (this.isRegisterMode) {
            title.textContent = 'Admin Registration';
            subtitle.textContent = 'Create new administrator credentials';
            submitBtn.textContent = 'Register';
            toggleLink.innerHTML = 'Already have an account? Login';
            this.ui.authUsername.value = '';
        } else {
            title.textContent = 'Admin Login';
            subtitle.textContent = 'Verify credentials to unlock controls';
            submitBtn.textContent = 'Login';
            toggleLink.innerHTML = "Don't have an account? Register";
            this.ui.authUsername.value = 'admin';
        }
        this.ui.authPassword.value = '';
    }

    async handleLogin() {
        const username = this.ui.authUsername.value.trim();
        const password = this.ui.authPassword.value;
        if (!username || !password) {
            this.ui.showToast('Please fill out both username and password.');
            return;
        }

        const endpoint = this.isRegisterMode ? '/api/register' : '/api/login';

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || (this.isRegisterMode ? 'Registration failed.' : 'Login failed. Invalid credentials.'));
            }

            if (this.isRegisterMode) {
                this.ui.showToast('Registration successful! You can now log in.', 'success');
                this.toggleAuthMode();
            } else {
                const data = await response.json();
                this.token = data.token;
                localStorage.setItem('jwt_token', this.token);
                this.ui.showToast('Logged in successfully!', 'success');
                this.checkAuth();
            }
        } catch (error) {
            console.error(error);
            this.ui.showToast(error.message);
        }
    }

    getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
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
                    language: data.language,
                    emotion: data.emotion
                });
                this.ui.updateMetrics(undefined, data.language, data.emotion);
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
            case 'session_analytics':
                this.ui.updateMetrics(undefined, undefined, data.overall_emotion);
                this.ui.addMessage('System', `Overall Call Emotion: ${data.overall_emotion}. Summary: ${data.summary}`, {});
                this.ui.setStatus('Call analyzed successfully');
                break;
            case 'error':
                this.ui.showToast(data.error_message || 'Pipeline Error', 'error');
                this.ui.setStatus('Error occurred');
                break;
        }
    }

    async joinCall() {
        this.ui.setConnectionState('connecting');
        this.ui.updateMetrics(0, '-', '-');
        try {
            // 1. Get Token from Backend
            const response = await fetch(`${this.API_BASE}/join`, { 
                method: 'POST',
                headers: this.getAuthHeaders()
            });
            if (response.status === 401 || response.status === 403) {
                this.token = '';
                localStorage.removeItem('jwt_token');
                this.checkAuth();
                throw new Error('Authentication expired or invalid. Please log in again.');
            }
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

    async callPhone() {
        const phoneNumber = this.ui.phoneInput.value.trim();
        if (!phoneNumber) {
            this.ui.showToast('Please enter a phone number in E.164 format (e.g. +91XXXXXXXXXX)');
            return;
        }

        this.ui.setConnectionState('connecting');
        this.ui.setStatus('Dialing phone...', true, false);
        this.ui.updateMetrics(0, '-', '-');

        try {
            const response = await fetch('/api/twilio/outbound', {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({ phoneNumber: phoneNumber })
            });

            if (response.status === 401 || response.status === 403) {
                this.token = '';
                localStorage.removeItem('jwt_token');
                this.checkAuth();
                throw new Error('Authentication expired or invalid. Please log in again.');
            }

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to place outbound call');
            }

            const data = await response.json();
            this.ui.showToast('Outbound call triggered successfully!', 'success');
            
            // Set connection state to connected when Twilio call connects (indicated by WebSocket bridge events downstream)
            this.ui.setConnectionState('connected');
            this.ui.setStatus('Call active on SIM. Talking...', false, true);

        } catch (error) {
            console.error(error);
            this.ui.showToast(error.message);
            this.ui.setConnectionState('disconnected');
        }
    }

    handleCallingModeChange(mode) {
        if (mode === 'webrtc') {
            this.ui.btnJoin.classList.remove('hidden');
            if (this.ui.phoneInputContainer) this.ui.phoneInputContainer.classList.add('hidden');
        } else if (mode === 'twilio_outbound') {
            this.ui.btnJoin.classList.add('hidden');
            if (this.ui.phoneInputContainer) this.ui.phoneInputContainer.classList.remove('hidden');
        }
    }
}

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    const ui = new UIManager();
    window.app = new VoicePipelineClient(ui);
});
