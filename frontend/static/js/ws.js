/**
 * Shared WebSocket Client with Auto-Reconnect & Web Audio Synthesizer
 */

class QuizWS {
  constructor(endpoint, onMessage, onStatusChange) {
    this.endpoint = endpoint;
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange || (() => {});
    this.ws = null;
    this.reconnectTimer = null;
    this.isConnected = false;
    this.connect();
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}${this.endpoint}`;

    try {
      this.ws = new WebSocket(url);
    } catch (e) {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.isConnected = true;
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      this.onStatusChange(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (err) {
        console.error('Invalid JSON received:', event.data);
      }
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.onStatusChange(false);
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws.close();
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, 2000);
  }
}

// Web Audio API Synthesizer (Instant procedural audio, zero external assets)
class SoundFX {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playTone(freq, duration, type = 'sine', gainVal = 0.2) {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  playPress() {
    this.playTone(520, 0.08, 'triangle', 0.25);
  }

  playStart() {
    this.playTone(440, 0.12, 'sine', 0.2);
    setTimeout(() => this.playTone(660, 0.15, 'sine', 0.25), 100);
    setTimeout(() => this.playTone(880, 0.25, 'sine', 0.3), 200);
  }

  playTick() {
    this.playTone(750, 0.04, 'triangle', 0.15);
  }

  playCorrect() {
    this.playTone(587.33, 0.15, 'sine', 0.3); // D5
    setTimeout(() => this.playTone(739.99, 0.15, 'sine', 0.35), 120); // F#5
    setTimeout(() => this.playTone(880.00, 0.35, 'sine', 0.4), 240); // A5
  }

  playIncorrect() {
    this.playTone(330, 0.2, 'sawtooth', 0.2);
    setTimeout(() => this.playTone(260, 0.35, 'sawtooth', 0.25), 150);
  }
}

window.soundFX = new SoundFX();
