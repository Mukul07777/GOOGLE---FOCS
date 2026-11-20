/**
 * The voice lane's recorder: the lecture tab's sound, in pieces of ~25 seconds.
 *
 * Each piece is a complete WebM file. A MediaRecorder with a timeslice puts the file header only in its first piece,
 * and the speech service rejects the others, so instead the recorder is stopped and started again for every piece.
 * While a piece records, its loudness is sampled; a piece that stayed quiet is dropped here and never sent, so music
 * breaks and silence cost nothing. If the page can't measure loudness (an AudioContext the browser keeps suspended),
 * every piece is sent and the server's own filter takes over.
 */
export interface AudioPiece { blob: Blob; startS: number; endS: number }

const MIME = typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported?.("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";

export class SpeechChunker {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sampler: number | null = null;
  private timer: number | null = null;
  private loudest = 0;
  private sampled = false;  // loudness was measured during this piece (else the piece is sent regardless)
  private pieceStart = 0;
  private running = false;
  private paused = false;

  constructor(track: MediaStreamTrack, private onPiece: (p: AudioPiece) => void, private clock: () => number,
    private seconds = 25, private quiet = 0.012) {
    this.stream = new MediaStream([track]);
  }

  static supported(): boolean {
    return typeof MediaRecorder !== "undefined";
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    try {
      this.ctx = new AudioContext();
      void this.ctx.resume().catch(() => undefined);
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 2048;
      this.ctx.createMediaStreamSource(this.stream).connect(this.analyser);  // (not to the speakers: the tab plays itself)
      const buf = new Float32Array(this.analyser.fftSize);
      this.sampler = window.setInterval(() => {
        if (this.ctx?.state !== "running") return;
        this.sampled = true;
        this.analyser!.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        this.loudest = Math.max(this.loudest, Math.sqrt(sum / buf.length));
      }, 200);
    } catch {
      this.ctx = null;  // can't measure: send every piece
    }
    this.next();
  }

  private next(): void {
    if (!this.running || this.paused) return;
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(this.stream, { mimeType: MIME, audioBitsPerSecond: 32000 });
    this.recorder = rec;
    this.loudest = 0;
    this.sampled = false;
    this.pieceStart = this.clock();
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      const endS = this.clock();
      const blob = new Blob(chunks, { type: MIME });
      if (blob.size && (!this.sampled || this.loudest >= this.quiet)) this.onPiece({ blob, startS: this.pieceStart, endS });
      this.next();
    };
    rec.start();
    this.timer = window.setTimeout(() => { if (rec.state !== "inactive") rec.stop(); }, this.seconds * 1000);
  }

  private flush(): void {
    if (this.timer) window.clearTimeout(this.timer);
    this.timer = null;
    if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
  }

  /** Lecture paused: send what was heard so far and stop recording until resumed. */
  pause(): void {
    if (this.paused) return;
    this.paused = true;
    this.flush();
  }

  resume(): void {
    if (!this.paused) return;
    this.paused = false;
    if (this.running) this.next();
  }

  stop(): void {
    this.running = false;
    this.flush();
    if (this.sampler) window.clearInterval(this.sampler);
    void this.ctx?.close().catch(() => undefined);
  }
}
