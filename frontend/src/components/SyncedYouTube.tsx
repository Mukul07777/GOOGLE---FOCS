import { Play, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { Button } from "@/components/ui/button";

/* Minimal typing for the YouTube IFrame API. */
export interface YTPlayer {
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  getPlayerState(): number;
  setPlaybackRate(rate: number): void;
  getPlaybackRate(): number;
  destroy(): void;
}
declare global {
  interface Window {
    YT?: { Player: new (el: HTMLElement, opts: Record<string, unknown>) => YTPlayer };
    onYouTubeIframeAPIReady?: () => void;
  }
}
const PLAYING = 1;
const PAUSED = 2;

let apiPromise: Promise<void> | null = null;
export function loadApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  if (!apiPromise) {
    apiPromise = new Promise((resolve) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(s);
    });
  }
  return apiPromise;
}

export interface VideoState {
  id: string | null;
  title: string | null;
  playing: boolean;
  position: number;
  updated_at: number;
  server_now: number;
  captions?: boolean;
  rate?: number;
}

/** Where the room's video is right now, in this browser's clock. */
export function expectedPosition(v: VideoState, skew: number) {
  const serverNow = Date.now() / 1000 + skew;
  return v.position + (v.playing ? Math.max(0, serverNow - v.updated_at) * (v.rate ?? 1) : 0);
}

export type HostAction = "play" | "pause" | "sync" | "rate";
const DRIFT = 1.5; // seconds a member may drift before being pulled back

/**
 * A YouTube player kept in sync with the room.
 * Host: play/pause/speed plus a 2 s heartbeat (which also catches seeking) go to the room; the host's player
 * follows only server-initiated changes (the quiz pause and resume). Members follow every change — position,
 * play state and speed — and are pulled back when they drift more than DRIFT seconds.
 */
export function SyncedYouTube({ video, reason, skew, isHost, onHostEvent, frameRef }: {
  video: VideoState;
  reason: string;
  skew: number;
  isHost: boolean;
  onHostEvent: (action: HostAction, position: number, playing?: boolean, rate?: number) => void;
  /** the player's box, for capturing it (room board notes) */
  frameRef?: RefObject<HTMLDivElement | null>;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const player = useRef<YTPlayer | null>(null);
  const ready = useRef(false);
  const applying = useRef(false); // true while we move the player ourselves, so it isn't echoed back
  const latest = useRef(video);
  latest.current = video;
  const hostEvent = useRef(onHostEvent);
  hostEvent.current = onHostEvent;
  const [blocked, setBlocked] = useState(false);
  const [drift, setDrift] = useState(0);

  const apply = (v: VideoState) => {
    const p = player.current;
    if (!p || !ready.current) return;
    applying.current = true;
    const target = expectedPosition(v, skew);
    if ((v.rate ?? 1) !== p.getPlaybackRate()) p.setPlaybackRate(v.rate ?? 1);
    if (Math.abs(p.getCurrentTime() - target) > DRIFT) p.seekTo(target, true);
    if (v.playing) {
      p.playVideo();
      setTimeout(() => {
        const still = player.current;
        setBlocked(!!still && latest.current.playing && still.getPlayerState() !== PLAYING);
      }, 1500);
    } else {
      p.pauseVideo();
      setBlocked(false);
    }
    setTimeout(() => { applying.current = false; }, 800);
  };

  // one player per video id
  useEffect(() => {
    if (!video.id || !hostRef.current) return;
    let cancelled = false;
    const el = document.createElement("div");
    hostRef.current.innerHTML = "";
    hostRef.current.appendChild(el);
    loadApi().then(() => {
      if (cancelled || !window.YT) return;
      player.current = new window.YT.Player(el, {
        videoId: video.id,
        width: "100%",
        height: "100%",
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1, start: Math.floor(expectedPosition(latest.current, skew)) },
        events: {
          onReady: () => { ready.current = true; apply(latest.current); },
          onStateChange: (e: { data: number }) => {
            if (!isHost || applying.current || !player.current) return;
            const rate = player.current.getPlaybackRate();
            if (e.data === PLAYING) hostEvent.current("play", player.current.getCurrentTime(), true, rate);
            if (e.data === PAUSED) hostEvent.current("pause", player.current.getCurrentTime(), false, rate);
          },
          onPlaybackRateChange: (e: { data: number }) => {
            if (!isHost || applying.current || !player.current) return;
            hostEvent.current("rate", player.current.getCurrentTime(), player.current.getPlayerState() === PLAYING, e.data);
          },
        },
      });
    });
    return () => {
      cancelled = true;
      ready.current = false;
      player.current?.destroy();
      player.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.id]);

  useEffect(() => {
    if (!isHost || reason === "quiz" || reason === "resume") apply(video);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.playing, video.position, video.updated_at, reason]);

  // host heartbeat (covers seeking, which YouTube doesn't report; the server drops no-change beats)
  // / member drift correction
  useEffect(() => {
    const t = setInterval(() => {
      const p = player.current;
      if (!p || !ready.current) return;
      if (isHost) {
        if (!applying.current) hostEvent.current("sync", p.getCurrentTime(), p.getPlayerState() === PLAYING, p.getPlaybackRate());
        return;
      }
      const off = latest.current.playing ? p.getCurrentTime() - expectedPosition(latest.current, skew) : 0;
      setDrift(off);
      if (Math.abs(off) > DRIFT || (latest.current.rate ?? 1) !== p.getPlaybackRate()) apply(latest.current);
    }, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isHost, skew]);

  const inSync = Math.abs(drift) <= DRIFT;
  return (
    <div ref={frameRef} className="relative aspect-video w-full overflow-hidden rounded-xl bg-black">
      <div ref={hostRef} className="absolute inset-0 [&>iframe]:h-full [&>iframe]:w-full" />
      {!isHost && video.playing && (
        <button onClick={() => apply(latest.current)} title="Jump to where the room is"
          className="glass absolute right-2 top-2 z-10 flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[11px] font-medium">
          {inSync ? <span className="h-1.5 w-1.5 rounded-full bg-ok" /> : <RefreshCw className="h-3 w-3 animate-spin text-warn" />}
          {inSync ? "In sync" : "Re-syncing…"}{(video.rate ?? 1) !== 1 && <span className="text-muted">· {video.rate}×</span>}
        </button>
      )}
      {blocked && (
        <div className="absolute inset-0 grid place-items-center bg-black/60 backdrop-blur-sm">
          <Button variant="primary" size="lg" icon={<Play className="h-4 w-4" />} onClick={() => { setBlocked(false); player.current?.playVideo(); }}>
            Tap to join the lecture
          </Button>
        </div>
      )}
    </div>
  );
}
