/**
 * Browser-side lecture capture.
 *
 * - Shares a *tab or window* via getDisplayMedia, so browser chrome (tabs, URL bar) is never
 *   captured — the root cause of junk notes in the old full-screen OCR.
 * - Crops to the region the student drew around the board.
 * - Keeps a tiny 48x27 luminance signature on-device and skips frames whose board hasn't
 *   changed, so an idle lecture costs zero bandwidth and zero server work. (A 64-bit hash is
 *   too coarse here: one new line of writing often flips no bits at all.)
 */

export interface Region {
  x: number; // all normalised 0..1 relative to the video frame
  y: number;
  w: number;
  h: number;
}

/** Classroom mode: the board's four corners in the camera frame (0..1), marked once by the student. */
export type Corners = [number, number][];

export interface Grab {
  blob: Blob;
  signature: Uint8Array;
  width: number;
  height: number;
  /** the board's corners within this (cropped) image, for the server to straighten it */
  corners?: Corners;
}

const MAX_SIDE = 1600;
const SIG_W = 48;
const SIG_H = 27;

export function isCaptureSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getDisplayMedia;
}

/** Why tab sharing or the camera didn't start, in words a student can act on. */
export function shareFailure(e: unknown, camera = false): string {
  const name = (e as DOMException)?.name;
  if (name === "NotAllowedError" || name === "SecurityError")
    return camera
      ? "The camera is blocked. Allow it in the browser's site settings (the icon left of the address), then try again."
      : "Sharing was cancelled or blocked. Click again and pick the tab that plays your lecture, then press Share.";
  if (name === "AbortError") return "Sharing stopped before it began. Click again and pick the lecture tab.";
  if (name === "NotFoundError") return camera ? "No camera was found on this device." : "There was nothing to share. Open the lecture in another tab first.";
  if (name === "NotReadableError") return camera ? "Another app is using the camera. Close it and try again." : "The browser couldn't read that tab. Try another tab or restart the browser.";
  if (typeof window !== "undefined" && !window.isSecureContext) return "Sharing needs a secure (https) page. Open Focs at its https address.";
  return camera ? "The camera didn't start. Try again, or upload a board photo instead." : "Sharing didn't start. Try again, or use Chrome or Edge on a computer.";
}

/** Classroom mode needs a camera, which phones have even where tab sharing isn't possible. */
export function isCameraSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

export class LectureCapture {
  stream: MediaStream | null = null;
  video: HTMLVideoElement;
  private canvas = document.createElement("canvas");
  private sigCanvas = document.createElement("canvas");
  region: Region | null = null;
  onEnded?: () => void;

  constructor(video: HTMLVideoElement = document.createElement("video")) {
    this.video = video;
    this.sigCanvas.width = SIG_W;
    this.sigCanvas.height = SIG_H;
  }

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      // 30 frames a second: students watch the lecture in Focs's own preview, and at 5 it looked laggy. The board is
      // still read only every few seconds (Studio's tick), so the server does no more work.
      video: { frameRate: { ideal: 30, max: 30 }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      // the teacher's voice too (the voice lane); a window or screen share may come without it
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      systemAudio: "include",
      // Chromium hints: offer tabs first, hide the Focs tab itself.
      preferCurrentTab: false,
      selfBrowserSurface: "exclude",
      surfaceSwitching: "include",
    } as DisplayMediaStreamOptions);
    this.stream = stream;
    this.video.srcObject = stream;
    this.video.muted = true;
    await this.video.play();
    stream.getVideoTracks()[0]?.addEventListener("ended", () => {
      this.stream = null;
      this.onEnded?.();
    });
  }

  /**
   * Capture *this* tab, cropped to one element (a study room's video player). Chromium's Region Capture
   * crops the stream itself; elsewhere the element's on-screen box is used as the crop region on every grab.
   * Cross-origin iframes such as the YouTube player are included: tab capture sees the composited page.
   */
  async startThisTab(element: HTMLElement): Promise<void> {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: { ideal: 5, max: 10 } },
      audio: false,
      preferCurrentTab: true,
      selfBrowserSurface: "include",
    } as DisplayMediaStreamOptions);
    const track = stream.getVideoTracks()[0];
    type Croppable = MediaStreamTrack & { cropTo?: (target: unknown) => Promise<void> };
    const CropTarget = (window as unknown as { CropTarget?: { fromElement(el: Element): Promise<unknown> } }).CropTarget;
    if (CropTarget && (track as Croppable).cropTo) {
      await (track as Croppable).cropTo!(await CropTarget.fromElement(element));
    } else {
      this.regionOf = element;
    }
    this.stream = stream;
    this.video.srcObject = stream;
    this.video.muted = true;
    await this.video.play();
    track?.addEventListener("ended", () => {
      this.stream = null;
      this.onEnded?.();
    });
  }

  /** Classroom mode: a phone's back camera (and its mic, for the teacher's voice) pointed at a real board. */
  camera = false;
  corners: Corners | null = null;

  async startCamera(): Promise<void> {
    const video = { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } };
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video, audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true } });
    } catch (e) {
      if ((e as DOMException)?.name === "NotAllowedError" && !(await this.cameraAllowed())) throw e;
      stream = await navigator.mediaDevices.getUserMedia({ video });  // the mic was refused: board notes still work
    }
    this.camera = true;
    this.stream = stream;
    this.video.srcObject = stream;
    this.video.muted = true;
    await this.video.play();
    stream.getVideoTracks()[0]?.addEventListener("ended", () => {
      this.stream = null;
      this.onEnded?.();
    });
  }

  private async cameraAllowed(): Promise<boolean> {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      s.getTracks().forEach((t) => t.stop());
      return true;
    } catch {
      return false;
    }
  }

  /** Fallback crop: follow an element's box inside the captured viewport. */
  private regionOf: HTMLElement | null = null;

  private get crop(): Region {
    if (this.camera && this.corners) {  // the box around the marked board (a little margin), straightened on the server
      const xs = this.corners.map((c) => c[0]), ys = this.corners.map((c) => c[1]);
      const x = Math.max(0, Math.min(...xs) - 0.01), y = Math.max(0, Math.min(...ys) - 0.01);
      return { x, y, w: Math.min(1, Math.max(...xs) + 0.01) - x, h: Math.min(1, Math.max(...ys) + 0.01) - y };
    }
    if (this.regionOf) {
      const r = this.regionOf.getBoundingClientRect();
      const w = window.innerWidth, h = window.innerHeight;
      return { x: Math.max(0, r.left / w), y: Math.max(0, r.top / h), w: Math.min(1, r.width / w), h: Math.min(1, r.height / h) };
    }
    return this.region ?? { x: 0, y: 0, w: 1, h: 1 };
  }

  /** Move the live stream onto another <video> (sharing must start inside a click handler elsewhere). */
  attach(video: HTMLVideoElement): void {
    if (this.video === video) return;
    this.video = video;
    video.muted = true;
    video.srcObject = this.stream;
    void video.play().catch(() => undefined);
  }

  stop(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video.srcObject = null;
  }

  /** The shared tab's sound, when it was shared (the student can untick "Also share tab audio"). */
  get audioTrack(): MediaStreamTrack | null {
    return this.stream?.getAudioTracks()[0] ?? null;
  }

  get active(): boolean {
    return !!this.stream && this.video.videoWidth > 0;
  }

  get surface(): string {
    const settings = this.stream?.getVideoTracks()[0]?.getSettings() as MediaTrackSettings & { displaySurface?: string };
    return settings?.displaySurface ?? "unknown";
  }

  /** Current frame (cropped to the region) as JPEG + change signature. */
  async grab(quality = 0.86): Promise<Grab | null> {
    const vw = this.video.videoWidth;
    const vh = this.video.videoHeight;
    if (!vw || !vh) return null;
    const r = this.crop;
    const sx = Math.round(r.x * vw);
    const sy = Math.round(r.y * vh);
    const sw = Math.max(16, Math.round(r.w * vw));
    const sh = Math.max(16, Math.round(r.h * vh));
    const scale = Math.min(1, MAX_SIDE / Math.max(sw, sh));
    this.canvas.width = Math.round(sw * scale);
    this.canvas.height = Math.round(sh * scale);
    const ctx = this.canvas.getContext("2d", { willReadFrequently: false })!;
    ctx.drawImage(this.video, sx, sy, sw, sh, 0, 0, this.canvas.width, this.canvas.height);

    const signature = this.signature(sx, sy, sw, sh);
    const blob = await new Promise<Blob | null>((res) => this.canvas.toBlob(res, "image/jpeg", quality));
    if (!blob) return null;
    const corners = this.camera && this.corners
      ? this.corners.map(([x, y]) => [(x - r.x) / r.w, (y - r.y) / r.h] as [number, number]) : undefined;
    return { blob, signature, width: this.canvas.width, height: this.canvas.height, corners };
  }

  /** Cheap signature for change detection, computed without encoding a JPEG. */
  peek(): Uint8Array | null {
    const vw = this.video.videoWidth;
    const vh = this.video.videoHeight;
    if (!vw || !vh) return null;
    const r = this.crop;
    return this.signature(r.x * vw, r.y * vh, Math.max(16, r.w * vw), Math.max(16, r.h * vh));
  }

  private signature(sx: number, sy: number, sw: number, sh: number): Uint8Array {
    const ctx = this.sigCanvas.getContext("2d", { willReadFrequently: true })!;
    ctx.drawImage(this.video, sx, sy, sw, sh, 0, 0, SIG_W, SIG_H);
    const px = ctx.getImageData(0, 0, SIG_W, SIG_H).data;
    const out = new Uint8Array(SIG_W * SIG_H);
    for (let i = 0; i < out.length; i++) out[i] = px[i * 4] * 0.299 + px[i * 4 + 1] * 0.587 + px[i * 4 + 2] * 0.114;
    return out;
  }
}

/**
 * True when the middle of the shared tab is black: the video there has gone into picture-in-picture
 * (Chrome moves a playing video into its own small window when you switch tabs), so the tab shows nothing.
 */
export function looksBlank(sig: Uint8Array | null): boolean {
  if (!sig) return false;
  let dark = 0, cells = 0;
  for (let y = Math.floor(SIG_H * 0.25); y < Math.ceil(SIG_H * 0.75); y++)
    for (let x = Math.floor(SIG_W * 0.2); x < Math.ceil(SIG_W * 0.8); x++, cells++) if (sig[y * SIG_W + x] < 24) dark++;
  return dark / cells >= 0.95;
}

/**
 * True when enough cells changed noticeably. Video compression jitters every cell by a few
 * levels, so we count cells that moved more than `delta`, not the average difference.
 */
export function boardChanged(a: Uint8Array | null, b: Uint8Array | null, delta = 14, minFraction = 0.004): boolean {
  if (!a || !b || a.length !== b.length) return true;
  let changed = 0;
  for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > delta) changed++;
  return changed / a.length >= minFraction;
}
