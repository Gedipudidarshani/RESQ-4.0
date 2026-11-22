/**
 * RESQ 4.0 Voice & Speech Intelligence Interface
 * Handles real-time microphone recording, Web Audio API waveform visualization,
 * Web Speech API recognition (Tamil & English), and Text-to-Speech synthesis.
 */
class VoiceIntelligenceInterface {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioContext = null;
        this.analyser = null;
        this.animationId = null;
        this.speechRecognition = null;
        this.selectedLanguage = 'en';
        this.onTranscriptCallback = null;
        
        this.initSpeechRecognition();
    }

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.speechRecognition = new SpeechRecognition();
            this.speechRecognition.continuous = true;
            this.speechRecognition.interimResults = true;
            this.speechRecognition.lang = this.selectedLanguage === 'ta' ? 'ta-IN' : 'en-US';

            this.speechRecognition.onresult = (event) => {
                let current = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    current += event.results[i][0].transcript;
                }
                if (this.onTranscriptCallback && current.trim()) {
                    this.onTranscriptCallback(current.trim(), false);
                }
            };

            this.speechRecognition.onerror = (e) => {
                console.warn('Speech recognition warning/error:', e.error);
            };
        }
    }

    setLanguage(lang) {
        this.selectedLanguage = lang;
        if (this.speechRecognition) {
            this.speechRecognition.lang = lang === 'ta' ? 'ta-IN' : 'en-US';
        }
    }

    async toggleRecording(canvasId, onTranscript) {
        this.onTranscriptCallback = onTranscript;
        if (!this.isRecording) {
            await this.startRecording(canvasId);
            return true;
        } else {
            this.stopRecording();
            return false;
        }
    }

    async startRecording(canvasId) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.isRecording = true;
            this.audioChunks = [];

            // Web Audio API setup for waveform
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);

            this.drawWaveform(canvasId);

            if (this.speechRecognition) {
                try { this.speechRecognition.start(); } catch (e) {}
            }
        } catch (err) {
            console.warn('Microphone permission not granted or unavailable, using simulation mode:', err);
            this.simulateWaveform(canvasId);
            this.isRecording = true;
        }
    }

    stopRecording() {
        this.isRecording = false;
        if (this.animationId) cancelAnimationFrame(this.animationId);
        if (this.speechRecognition) {
            try { this.speechRecognition.stop(); } catch (e) {}
        }
        if (this.audioContext && this.audioContext.state !== 'closed') {
            try { this.audioContext.close(); } catch (e) {}
        }
    }

    drawWaveform(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !this.analyser) return;
        const ctx = canvas.getContext('2d');
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const render = () => {
            if (!this.isRecording) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                return;
            }
            this.animationId = requestAnimationFrame(render);
            this.analyser.getByteFrequencyData(dataArray);

            ctx.fillStyle = '#090e1a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.5;
            let barHeight;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                barHeight = dataArray[i] / 2;
                ctx.fillStyle = `rgb(${barHeight + 40}, 182, 212)`;
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                x += barWidth + 1;
            }
        };
        render();
    }

    simulateWaveform(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        const render = () => {
            if (!this.isRecording) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                return;
            }
            this.animationId = requestAnimationFrame(render);
            ctx.fillStyle = '#090e1a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const barCount = 32;
            const barWidth = canvas.width / barCount;
            for (let i = 0; i < barCount; i++) {
                const height = Math.random() * (canvas.height * 0.8);
                ctx.fillStyle = '#06b6d4';
                ctx.fillRect(i * barWidth, canvas.height - height, barWidth - 2, height);
            }
        };
        render();
    }

    speak(text, lang = 'en') {
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang === 'ta' ? 'ta-IN' : 'en-US';
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
    }
}

const voiceInterface = new VoiceIntelligenceInterface();
