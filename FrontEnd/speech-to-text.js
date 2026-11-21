/*
 * SignConnect - microphone speech-to-text (chunked, near-real-time).
 *
 * How it works:
 *   1. Records the microphone with MediaRecorder.
 *   2. Watches the volume with an AnalyserNode. When you pause (silenceMs of quiet after speech)
 *      or a chunk reaches maxChunkMs, it stops the recorder -> one complete, standalone audio file.
 *   3. Sends that file to the FastAPI backend (/api/stt/transcribe), which calls Groq Whisper.
 *   4. Starts a fresh recorder immediately, so listening continues.
 *
 * Silent chunks are never uploaded, which saves the free quota and avoids Whisper's
 * habit of inventing words in silence. Results are delivered in order.
 *
 * No API key here - the browser only ever talks to your own backend.
 *
 * Usage (plain <script> tag, no bundler needed):
 *   const stt = new SpeechToText({
 *     stream: localStream,          // optional: reuse an existing mic/camera stream
 *     onText: (text) => { captions.textContent += " " + text; },
 *     onStatus: (s) => console.log(s),
 *     onError: (msg) => alert(msg),
 *   });
 *   await stt.start();   // must be called from a user gesture (button click)
 *   stt.stop();
 *
 * Push-to-talk instead of auto-chunking: pass { silenceMs: Infinity, maxChunkMs: 60000 },
 * call start() on mousedown and stop() on mouseup.
 */
(function () {
  "use strict";

  const DEFAULTS = {
    apiBase: "",                 // same origin: proxy.py forwards /api/* to FastAPI
    endpoint: "/api/stt/transcribe",
    getToken: () => localStorage.getItem("access_token"), // key used by auth.js
    stream: null,                // pass an existing MediaStream to reuse its audio track
    language: "en",          // null = let Whisper auto-detect
    silenceThreshold: 0.015, // RMS level (0..1) counted as "speaking"; raise it in noisy rooms
    silenceMs: 800,          // this much quiet after speech ends a chunk
    minSpeechMs: 300,        // chunks with less speech than this are dropped
    maxChunkMs: 15000,       // hard cap on chunk length
    onText: () => {},
    onStatus: () => {},
    onError: (msg) => console.error("[SpeechToText]", msg),
  };

  const MIME_CANDIDATES = [
    "audio/webm;codecs=opus", // Chrome, Edge, Firefox
    "audio/ogg;codecs=opus",  // Firefox
    "audio/mp4",              // Safari
    "audio/webm",
  ];

  function pickMimeType() {
    return MIME_CANDIDATES.find((t) => MediaRecorder.isTypeSupported(t)) || "";
  }

  function extensionFor(mime) {
    if (mime.includes("ogg")) return "ogg";
    if (mime.includes("mp4")) return "mp4";
    return "webm";
  }

  class SpeechToText {
    constructor(options = {}) {
      this.o = { ...DEFAULTS, ...options };
      this.running = false;
      this.sendQueue = Promise.resolve();
    }

    async start() {
      if (this.running) return;
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error("This browser cannot record audio.");
      }

      const external = this.o.stream && this.o.stream.getAudioTracks().length > 0;
      this.ownsStream = !external;
      this.stream = external
        // Audio-only copy of the shared stream: same mic, no video in the recording.
        ? new MediaStream(this.o.stream.getAudioTracks())
        : await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
          });
      this.mimeType = pickMimeType();

      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = this.audioCtx.createMediaStreamSource(this.stream);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 2048;
      source.connect(this.analyser);
      this.samples = new Float32Array(this.analyser.fftSize);

      this.running = true;
      this._startChunk();
      this.lastTick = performance.now();
      this.timer = setInterval(() => this._tick(), 50);
      this.o.onStatus("listening");
    }

    stop() {
      if (!this.running) return;
      this.running = false;
      clearInterval(this.timer);
      if (this.recorder && this.recorder.state === "recording") this.recorder.stop(); // flushes last chunk
      if (this.ownsStream) this.stream.getTracks().forEach((t) => t.stop()); // never stop the call's mic
      this.audioCtx.close();
      this.o.onStatus("stopped");
    }

    // ---- internals -------------------------------------------------------

    _startChunk() {
      const recorder = new MediaRecorder(this.stream, this.mimeType ? { mimeType: this.mimeType } : undefined);
      const parts = [];
      const chunk = { startedAt: performance.now(), speechMs: 0, lastVoiceAt: null };

      recorder.ondataavailable = (e) => { if (e.data && e.data.size) parts.push(e.data); };
      recorder.onstop = () => {
        if (chunk.speechMs >= this.o.minSpeechMs && parts.length) {
          const blob = new Blob(parts, { type: recorder.mimeType || this.mimeType || "audio/webm" });
          this.sendQueue = this.sendQueue.then(() => this._send(blob));
        }
        if (this.running) this._startChunk();
      };

      this.recorder = recorder;
      this.chunk = chunk;
      recorder.start();
    }

    _tick() {
      const now = performance.now();
      const dt = now - this.lastTick;
      this.lastTick = now;

      this.analyser.getFloatTimeDomainData(this.samples);
      let sum = 0;
      for (let i = 0; i < this.samples.length; i++) sum += this.samples[i] * this.samples[i];
      const rms = Math.sqrt(sum / this.samples.length);

      const c = this.chunk;
      if (rms > this.o.silenceThreshold) {
        c.speechMs += dt;
        c.lastVoiceAt = now;
      }

      const pausedAfterSpeech = c.lastVoiceAt !== null && now - c.lastVoiceAt > this.o.silenceMs;
      const tooLong = now - c.startedAt > this.o.maxChunkMs;
      if ((pausedAfterSpeech || tooLong) && this.recorder.state === "recording") {
        this.recorder.stop(); // onstop uploads (if speech) and starts the next chunk
      }
    }

    async _send(blob) {
      const form = new FormData();
      form.append("file", blob, `chunk.${extensionFor(blob.type)}`);
      if (this.o.language) form.append("language", this.o.language);

      const headers = {};
      const token = this.o.getToken && this.o.getToken();
      if (token) headers.Authorization = `Bearer ${token}`;

      this.o.onStatus("transcribing");
      try {
        const res = await fetch(this.o.apiBase + this.o.endpoint, { method: "POST", body: form, headers });
        if (res.status === 429) {
          const wait = res.headers.get("Retry-After");
          this.o.onError(`Speech-to-text limit reached${wait ? `; retry in ${wait}s` : ""}.`);
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.o.onError(body.detail || `Transcription failed (${res.status}).`);
          return;
        }
        const { text } = await res.json();
        if (text) this.o.onText(text);
      } catch (err) {
        this.o.onError("Network error while transcribing.");
      } finally {
        if (this.running) this.o.onStatus("listening");
      }
    }
  }

  window.SpeechToText = SpeechToText;
})();
