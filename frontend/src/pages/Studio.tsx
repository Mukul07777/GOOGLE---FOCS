import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bell, Camera, Check, CircleStop, ClipboardPaste, Crop, Crosshair, Eye, Gauge, Image as ImageIcon, Layers, Lightbulb, Link2, Loader2, MessageCircleQuestion, Mic, MonitorPlay, Pause, Pencil, PictureInPicture2, Play, Smartphone, Sparkles, Target, Upload, Zap } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Companion, type FocusNote } from "@/components/Companion";
import { LiveQuizDialog, MiniPanel, usePipWindow, type LiveQuestion } from "@/components/LiveQuiz";
import { Lightbox } from "@/components/common";
import { FocusBar, FocusButton, NotesSheet, useLectureFocus, useUnseen } from "@/components/LectureFocus";
import { LinkStudio } from "@/components/LinkStudio";
import { NoteCard } from "@/components/NoteCard";
import { RevisionSheet } from "@/components/RevisionSheet";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, EmptyState, Input, Label, Segmented, Select, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { boardChanged, isCameraSupported, isCaptureSupported, LectureCapture, looksBlank, shareFailure, type Corners, type Region } from "@/lib/capture";
import type { FrameResponse, FrameStatus, SessionEnd, StudySession, LectureSegment } from "@/lib/types";
import { clockAt, cn, formatDuration, formatPaused, hasSyllabus } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { forgetLive, recallLive, rememberLive, steadyInterval, useFocus, useSessionAlive, useWakeLock, welcomeBack } from "@/lib/focus";
import { PauseNotice, StageCard } from "@/components/PauseNotice";
import { bindingMeter, useUsage } from "@/components/UsageMeter";
import { SpeechChunker } from "@/lib/audio";
import type { Confidence } from "@/components/ConfidenceLock";
import { CalibrationCard } from "@/components/CalibrationCard";
import { useT } from "@/lib/i18n";
import { slowConnection } from "@/lib/offline";

// only for a student with no syllabus on Focs (Other, UPSC, CA): everyone else picks from their own subjects
const OPEN_SUBJECTS = ["Physics", "Chemistry", "Mathematics", "Biology", "Computer Science", "Economics", "Commerce", "General"];

/* ================================================================== photo upload */
function PhotoDialog({ open, onClose, sessionId }: { open: boolean; onClose: () => void; sessionId?: number }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<FrameResponse | null>(null);
  const [drag, setDrag] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) return toast.error("Please choose an image");
    setFile(f);
    setResult(null);
    setPreview(URL.createObjectURL(f));
  };
  const upload = useMutation({
    mutationFn: () => api.sendPhoto(file!, sessionId),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ["overview"] });
      if (sessionId) qc.invalidateQueries({ queryKey: ["session", sessionId] });
      if (r.status !== "created") toast.message(r.status === "no_text" ? "No readable text found in that photo" : "That photo didn't look like lecture content");
    },
  });
  const reset = () => { setFile(null); setPreview(null); setResult(null); };

  return (
    <Dialog open={open} onClose={() => { reset(); onClose(); }} wide title="Board photo → notes"
      subtitle="Snap the board in an offline class, or upload a notebook page. Focs reads it and writes notes.">
      {!result?.note ? (
        <div className="space-y-4">
          <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
            className={cn("relative flex min-h-64 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed transition",
              drag ? "border-accent bg-accent-soft" : "border-line-strong bg-bg-soft hover:border-accent/50")}>
            {preview ? <img src={preview} alt="" className="max-h-80 w-full object-contain" /> : (
              <>
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent-soft text-accent"><Upload className="h-5 w-5" /></div>
                <div className="mt-3 text-sm font-medium">Drop a photo, or click to choose</div>
                <div className="mt-1 text-xs text-muted">On your phone this opens the camera · JPG, PNG, WebP up to 12 MB</div>
              </>
            )}
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            {upload.isPending && <div className="absolute inset-0 grid place-items-center bg-bg/70 backdrop-blur-sm"><span className="flex items-center gap-2 text-sm font-medium"><Loader2 className="h-4 w-4 animate-spin text-accent" />Reading the board…</span></div>}
          </label>
          <div className="flex justify-end gap-2">
            {file && <Button variant="ghost" onClick={reset}>Choose another</Button>}
            <Button variant="primary" disabled={!file} loading={upload.isPending} onClick={() => upload.mutate()} icon={<Sparkles className="h-4 w-4" />}>Make notes</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <NoteCard note={result.note} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={reset}>Add another photo</Button>
            {!sessionId && result.session_id && (
              <Button variant="primary" onClick={() => { onClose(); navigate(`/app/library/${result.session_id}`); }}>Open in library <ArrowRight className="h-4 w-4" /></Button>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

const youtubeLink = (text: string) => /https?:\/\/\S*(?:youtube\.com|youtu\.be)\S*/i.exec(text)?.[0] ?? "";

/* ================================================================== start screen */
function StartScreen({ onStarted, onPhoto }: { onStarted: (s: StudySession, c: LectureCapture | null) => void; onPhoto: () => void }) {
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);  // why the last try to share or film didn't start
  const supported = isCaptureSupported();
  const cameraOk = isCameraSupported();
  const [shared, setShared] = useSearchParams();
  // "Share" on a YouTube video in another app: the phone hands the link to Focs, in any of these three fields
  const [link, setLink] = useState(() => youtubeLink(`${shared.get("shared_url") ?? ""} ${shared.get("shared_text") ?? ""} ${shared.get("shared_title") ?? ""}`));
  const [linkOpen, setLinkOpen] = useState(!supported || !!link);  // a phone can't share a tab: the link is its way in
  useEffect(() => {
    if (shared.has("shared_url") || shared.has("shared_text")) setShared({}, { replace: true });
  }, [shared, setShared]);
  const canPaste = !!navigator.clipboard?.readText;
  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setLink(youtubeLink(text) || text.trim());
    } catch {
      toast.info("Paste it into the box: long-press, then Paste.");
    }
  };
  const ownSyllabus = useAuth((s) => hasSyllabus(s.user?.exam_target));
  const { data: tree } = useQuery({ queryKey: ["prep-syllabus"], queryFn: () => api.prepSyllabus(), enabled: ownSyllabus, staleTime: 60_000 });
  const subjects = ownSyllabus ? [...(tree?.subjects ?? []).map((s) => s.name), "General"] : OPEN_SUBJECTS;

  /** Lecture by link: the YouTube lecture plays inside Focs, and notes are written as it plays (works on phones). */
  const fromLink = async () => {
    if (!link.trim()) return;
    setBusy(true);
    setFailed(null);
    try {
      const s = await api.startSession({ title: title.trim() || undefined, subject: subject || undefined, source: "link", video_url: link.trim() });
      onStarted(s, null);
    } catch (e) {
      const why = e instanceof Error ? e.message : "Couldn't start the lecture";
      setFailed(why);
      toast.error(why);
    } finally {
      setBusy(false);
    }
  };

  /** Classroom mode: a phone (or laptop camera) pointed at a real board, with its mic for the teacher's voice. */
  const classroom = async () => {
    setBusy(true);
    setFailed(null);
    const capture = new LectureCapture();
    try {
      await capture.startCamera();  // inside the click, like tab sharing
    } catch (e) {
      setBusy(false);
      const why = shareFailure(e, true);
      setFailed(why);
      return toast.error(why);
    }
    try {
      const s = await api.startSession({ title: title.trim() || undefined, subject: subject || undefined, source: "camera" });
      onStarted(s, capture);
    } catch (e) {
      capture.stop();
      toast.error(e instanceof Error ? e.message : "Couldn't start the session");
    } finally {
      setBusy(false);
    }
  };

  const share = async () => {
    setBusy(true);
    setFailed(null);
    const capture = new LectureCapture();
    try {
      await capture.start(); // must run inside the click: browsers require a user gesture
    } catch (e) {
      setBusy(false);
      const why = shareFailure(e);
      setFailed(why);
      return toast.error(why);
    }
    try {
      const s = await api.startSession({ title: title.trim() || undefined, subject: subject || undefined, source: "screen" });
      onStarted(s, capture);
    } catch (e) {
      capture.stop();
      toast.error(e instanceof Error ? e.message : "Couldn't start the session");
    } finally {
      setBusy(false);
    }
  };

  const t = useT();
  return (
    <div className="mx-auto max-w-4xl">
      <div className="text-center">
        <Badge tone="accent"><Zap className="h-3 w-3" /> {t("Live lecture")}</Badge>
        <h1 className="mt-4 text-[36px] sm:text-[46px]">{t("What are we studying?")}</h1>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted">{t("Share the tab that's playing your lecture. Focs reads the board, writes your notes and pops quick quizzes while you watch.")}</p>
      </div>

      <Card className="mt-8 p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1.6fr_1fr]">
          <div><Label hint={t("optional")}>{t("Lecture title")}</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Rotational Motion — Lecture 4" /></div>
          <div>
            <Label>{t("Subject")}</Label>
            <Select aria-label={t("Subject")} value={subject} onChange={(e) => setSubject(e.target.value)}>
              <option value="">{t("Detect automatically")}</option>
              {subjects.map((s) => <option key={s}>{s}</option>)}
            </Select>
          </div>
        </div>
        <div className={cn("mt-6 rounded-2xl border p-4 sm:p-5", linkOpen ? "border-accent/40 bg-accent-soft/40" : "border-line bg-bg-soft")}>
          <button type="button" className="flex w-full items-center gap-3 text-left" onClick={() => setLinkOpen(true)} aria-expanded={linkOpen}>
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-brand text-brand-fg"><Link2 className="h-5 w-5" /></div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 font-semibold">{t("Paste a lecture link")}{!supported && <Badge tone="ok">{t("Works on phones")}</Badge>}</div>
              <p className="mt-0.5 text-[13px] text-muted">{t("A YouTube lecture plays right here, and Focs writes notes from the board and the teacher's voice as you watch.")}</p>
            </div>
          </button>
          {linkOpen && (
            <form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); void fromLink(); }}>
              <div className="relative min-w-0 flex-1">
                <Input value={link} onChange={(e) => setLink(e.target.value)} inputMode="url" autoComplete="off" enterKeyHint="go"
                  placeholder="https://youtu.be/…" aria-label={t("YouTube lecture link")} className={canPaste && !link ? "pr-20" : undefined} />
                {canPaste && !link && (
                  <button type="button" onClick={() => void paste()} className="absolute inset-y-0 right-0 flex items-center gap-1.5 px-3 text-[13px] font-medium text-fg-soft hover:text-fg">
                    <ClipboardPaste className="h-3.5 w-3.5" />{t("Paste")}
                  </button>
                )}
              </div>
              <Button type="submit" variant="primary" loading={busy} disabled={!link.trim()} icon={<Play className="h-4 w-4" />}>{t("Start watching")}</Button>
            </form>
          )}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <button onClick={share} disabled={!supported || busy}
            className={`ring-gradient group relative overflow-hidden rounded-2xl bg-elev p-5 text-left transition hover:bg-elev-2 disabled:opacity-50 ${supported ? "" : "order-last"}`}>
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-brand text-brand-fg"><MonitorPlay className="h-5 w-5" /></div>
            <div className="mt-4 flex items-center gap-2 font-semibold">{t(busy ? "Waiting for you to pick a tab…" : "Share a lecture tab")} <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" /></div>
            <p className="mt-1 text-[13px] text-muted">{t("YouTube, Physics Wallah, Unacademy, Zoom or Meet in the browser.")}</p>
          </button>
          <button onClick={classroom} disabled={!cameraOk || busy}
            className="group rounded-2xl border border-line bg-bg-soft p-5 text-left transition hover:border-line-strong hover:bg-elev-2 disabled:opacity-50">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-elev-2 text-accent"><Smartphone className="h-5 w-5" /></div>
            <div className="mt-4 flex items-center gap-2 font-semibold">{t("In a classroom")} <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" /></div>
            <p className="mt-1 text-[13px] text-muted">{t("Prop your phone on the desk, camera on the board. Ask your teacher first: their voice becomes captions and is never stored.")}</p>
          </button>
          <button onClick={onPhoto} className="group rounded-2xl border border-line bg-bg-soft p-5 text-left transition hover:border-line-strong hover:bg-elev-2">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-elev-2 text-accent-2"><Camera className="h-5 w-5" /></div>
            <div className="mt-4 flex items-center gap-2 font-semibold">{t("Upload a board photo")} <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" /></div>
            <p className="mt-1 text-[13px] text-muted">{t("For offline classes, coaching boards and notebook pages.")}</p>
          </button>
        </div>
        {failed && <p role="alert" className="mt-4 rounded-xl border border-bad/25 bg-bad/10 p-3 text-sm text-bad">{t(failed)}</p>}
        {!supported && <p className="mt-4 rounded-xl border border-line bg-bg-soft p-3 text-sm text-muted">{t("This browser can't share a tab (most phones can't).")} {t("Paste the lecture's link above instead.")} {cameraOk && t("In a real class, point the camera at the board.")}</p>}
      </Card>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          [Eye, "Choose a Tab, not the screen", "Tab capture never includes your browser's tabs or URL bar."],
          [Crop, "Crop to the board", "Drag a box over the board so faces and player controls are ignored."],
          [Zap, "Idle boards cost nothing", "Frames are only sent when the writing actually changes."],
        ].map(([Icon, title, b]) => {
          const I = Icon as typeof Eye;
          return (
            <div key={String(title)} className="rounded-2xl border border-line bg-bg-soft p-4">
              <I className="h-4 w-4 text-accent" />
              <div className="mt-2 text-sm font-medium">{t(String(title))}</div>
              <div className="mt-1 text-xs leading-relaxed text-muted">{t(String(b))}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ================================================================== region selector */
function useContentRect(video: HTMLVideoElement | null, box: HTMLDivElement | null) {
  const [rect, setRect] = useState({ ox: 0, oy: 0, dw: 0, dh: 0 });
  useEffect(() => {
    if (!video || !box) return;
    const update = () => {
      const vw = video.videoWidth, vh = video.videoHeight, cw = box.clientWidth, ch = box.clientHeight;
      if (!vw || !vh) return setRect({ ox: 0, oy: 0, dw: cw, dh: ch });
      const s = Math.min(cw / vw, ch / vh);
      setRect({ ox: (cw - vw * s) / 2, oy: (ch - vh * s) / 2, dw: vw * s, dh: vh * s });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(box);
    video.addEventListener("loadedmetadata", update);
    video.addEventListener("resize", update);
    return () => { ro.disconnect(); video.removeEventListener("loadedmetadata", update); video.removeEventListener("resize", update); };
  }, [video, box]);
  return rect;
}

function RegionSelector({ video, region, onChange, enabled }: {
  video: HTMLVideoElement | null; region: Region | null; onChange: (r: Region | null) => void; enabled: boolean;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<HTMLDivElement | null>(null);
  const { ox, oy, dw, dh } = useContentRect(video, box);
  const [draft, setDraft] = useState<Region | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  const norm = (e: ReactPointerEvent) => {
    const r = boxRef.current!.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left - ox) / dw)), y: Math.min(1, Math.max(0, (e.clientY - r.top - oy) / dh)) };
  };
  const shown = draft ?? region;

  return (
    <div ref={(el) => { boxRef.current = el; setBox(el); }} className={cn("absolute inset-0", enabled && "cursor-crosshair")}
      onPointerDown={(e) => { if (!enabled) return; (e.target as HTMLElement).setPointerCapture(e.pointerId); start.current = norm(e); setDraft(null); }}
      onPointerMove={(e) => {
        if (!start.current) return;
        const p = norm(e), s = start.current;
        setDraft({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
      }}
      onPointerUp={() => {
        if (draft && draft.w > 0.04 && draft.h > 0.04) onChange(draft);
        start.current = null;
        setDraft(null);
      }}>
      {shown && dw > 0 && (
        <div className="pointer-events-none absolute rounded-md border-2 border-accent-2"
          style={{ left: ox + shown.x * dw, top: oy + shown.y * dh, width: shown.w * dw, height: shown.h * dh, boxShadow: "0 0 0 9999px rgb(0 0 0 / 0.55)" }}>
          <span className="absolute -top-6 left-0 rounded-md bg-accent-2 px-1.5 py-0.5 text-[10.5px] font-semibold text-black">Board</span>
        </div>
      )}
    </div>
  );
}

const DEFAULT_CORNERS: Corners = [[0.12, 0.12], [0.88, 0.12], [0.88, 0.88], [0.12, 0.88]];
const CORNER_NAMES = ["top-left", "top-right", "bottom-right", "bottom-left"];

/** Classroom mode: drag (or move with the arrow keys) four handles onto the board's corners. Every frame is then
    straightened to a front-on board before it's read, so a phone at an angle reads like a camera facing the board. */
function CornerSelector({ video, corners, editing, onDone }: {
  video: HTMLVideoElement | null; corners: Corners | null; editing: boolean; onDone: (c: Corners) => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<HTMLDivElement | null>(null);
  const { ox, oy, dw, dh } = useContentRect(video, box);
  const [draft, setDraft] = useState<Corners>(corners ?? DEFAULT_CORNERS);
  const dragging = useRef<number | null>(null);
  useEffect(() => { if (editing) setDraft(corners ?? DEFAULT_CORNERS); }, [editing, corners]);
  const shown = editing ? draft : corners;
  if (!shown || dw <= 0) return <div ref={(el) => { boxRef.current = el; setBox(el); }} className="pointer-events-none absolute inset-0" />;
  const px = (c: [number, number]) => [ox + c[0] * dw, oy + c[1] * dh];
  const move = (i: number, x: number, y: number) =>
    setDraft((d) => d.map((c, j) => (j === i ? [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))] : c)) as Corners);
  const norm = (e: ReactPointerEvent) => {
    const r = boxRef.current!.getBoundingClientRect();
    return [(e.clientX - r.left - ox) / dw, (e.clientY - r.top - oy) / dh];
  };
  const poly = shown.map((c) => px(c).join(",")).join(" ");
  return (
    <div ref={(el) => { boxRef.current = el; setBox(el); }} className={cn("absolute inset-0", !editing && "pointer-events-none")}
      onPointerMove={(e) => { if (dragging.current !== null) { const [x, y] = norm(e); move(dragging.current, x, y); } }}
      onPointerUp={() => { dragging.current = null; }}>
      <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
        <defs><mask id="board-mask"><rect width="100%" height="100%" fill="white" /><polygon points={poly} fill="black" /></mask></defs>
        <rect width="100%" height="100%" fill="rgb(0 0 0 / 0.55)" mask="url(#board-mask)" />
        <polygon points={poly} fill="none" stroke="var(--accent-2)" strokeWidth="2" />
      </svg>
      {editing && shown.map((c, i) => {
        const [x, y] = px(c);
        return (
          <button key={i} type="button" aria-label={`Board corner, ${CORNER_NAMES[i]}. Drag, or move with the arrow keys`}
            className="absolute h-7 w-7 -translate-x-1/2 -translate-y-1/2 touch-none rounded-full border-2 border-white bg-accent-2 shadow-lg"
            style={{ left: x, top: y }}
            onPointerDown={(e) => { (e.target as HTMLElement).setPointerCapture(e.pointerId); dragging.current = i; }}
            onPointerUp={() => { dragging.current = null; }}
            onKeyDown={(e) => {
              const step = e.shiftKey ? 0.05 : 0.01;
              const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
              if (d) { e.preventDefault(); move(i, c[0] + d[0], c[1] + d[1]); }
            }} />
        );
      })}
      {editing && (
        <div className="glass absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full border border-line px-4 py-2 text-xs">
          <Crosshair className="h-3.5 w-3.5 text-accent-2" />
          <span>Put the four dots on the <b>board's corners</b></span>
          <Button size="sm" variant="primary" onClick={() => onDone(draft)}>Done</Button>
        </div>
      )}
    </div>
  );
}

function BasicModeBar() {
  const { data: u } = useUsage();
  const m = u ? bindingMeter(u).meter : null;
  return (
    <div className="flex items-center gap-2 border-b border-warn/25 bg-warn/10 px-4 py-2 text-xs text-warn">
      <Gauge className="h-3.5 w-3.5 shrink-0" />
      <span className="flex-1">AI allowance used — new boards get basic notes{m?.resets_at ? ` until ${clockAt(m.resets_at)}` : ""}.</span>
      <Link to="/app/settings#usage" className="font-semibold underline-offset-2 hover:underline">Plans</Link>
    </div>
  );
}

/* ================================================================== live studio */
const STATUS_TEXT: Record<FrameStatus | "idle" | "reading" | "error" | "paused" | "waiting" | "steadying", { text: string; tone: string }> = {
  idle: { text: "Waiting for the first board", tone: "text-muted" },
  waiting: { text: "Share your lecture tab to continue", tone: "text-warn" },
  steadying: { text: "Waiting for the camera to hold still", tone: "text-muted" },
  paused: { text: "Paused", tone: "text-warn" },
  reading: { text: "Reading the board…", tone: "text-accent-2" },
  unchanged: { text: "Board unchanged", tone: "text-muted" },
  busy: { text: "Still processing the previous board", tone: "text-muted" },
  no_text: { text: "No writing on the board yet", tone: "text-muted" },
  duplicate: { text: "Same board — nothing new", tone: "text-muted" },
  not_lecture: { text: "Not lecture content — ignored", tone: "text-warn" },
  created: { text: "New board captured", tone: "text-ok" },
  updated: { text: "Board grew — notes updated", tone: "text-ok" },
  growing: { text: "Following the board — its notes come when the teacher moves on", tone: "text-accent-2" },
  error: { text: "Couldn't process that frame", tone: "text-bad" },
};

type Voice = "off" | "listening" | "no_audio" | "unavailable" | "allowance" | "captions";

/** The teacher's words under the lecture, about half a minute behind (the voice lane), or why there are none. */
function CaptionsStrip({ voice, captions, onShareAgain }: { voice: Voice; captions: LectureSegment[]; onShareAgain: () => void }) {
  const t = useT();
  if (voice === "off") return null;
  return (
    <div className="border-t border-line px-4 py-3" aria-live="polite">
      <div className="mb-1 flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted">
        <Mic className="h-3.5 w-3.5 text-accent-2" />{t("What the teacher is saying")}{voice === "listening" && <span className="live-dot" />}
      </div>
      {voice === "listening" && (captions.length
        ? captions.map((c, i) => <p key={c.id} lang={c.language === "hi" ? "hi" : undefined} className={cn("text-[14px] leading-relaxed", i < captions.length - 1 ? "text-muted" : "text-fg")}>{c.text}</p>)
        : <p className="text-sm text-muted">Listening. Captions appear about half a minute behind the lecture; silence is skipped.</p>)}
      {voice === "no_audio" && (
        <p className="text-sm text-fg-soft">No lecture sound was shared, so Focs is reading the board only.{" "}
          <button className="font-medium text-accent hover:underline" onClick={onShareAgain}>Share again</button> and keep “Also share tab audio” ticked to get what the teacher says too.</p>
      )}
      {voice === "unavailable" && <p className="text-sm text-muted">Captions need speech-to-text, which isn't set up on this server (a Groq key turns it on). The board notes carry on.</p>}
      {voice === "allowance" && <p className="text-sm text-muted">Captions are paused: this window's AI allowance is used up. The board notes carry on.</p>}
      {voice === "captions" && <p className="text-sm text-muted">{t("This week's caption minutes are used up, so captions are paused. The board notes carry on; Pro has more caption time.")}</p>}
    </div>
  );
}

function LiveStudio({ session: initial, capture: initialCapture, onEnded, onPhoto, onGone, backAfter }: {
  session: StudySession; capture: LectureCapture | null; onEnded: (r: SessionEnd) => void; onPhoto: () => void; onGone: () => void; backAfter: number | null;
}) {
  const qc = useQueryClient();
  const [session, setSession] = useState(initial);
  const [capture, setCapture] = useState<LectureCapture | null>(initialCapture);
  const [sharing, setSharing] = useState(!!initialCapture?.stream);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [cropping, setCropping] = useState(false);
  // on a 2G or data-saver connection, frames go less often (the board changes slowly anyway)
  const [interval, setIntervalSec] = useState<"3" | "5" | "8">(() => (slowConnection() ? "8" : "5"));
  const [paused, setPaused] = useState(false);
  const [pausedAt, setPausedAt] = useState<number | null>(null);  // when Focs's own Pause was pressed
  const [stopped, setStopped] = useState<{ secs: number | null; back?: boolean } | null>(backAfter !== null ? { secs: backAfter, back: true } : null);
  const [gone, setGone] = useState(false);  // the server says this lecture was ended
  const [mutedAt, setMutedAt] = useState<number | null>(null);  // Chrome mutes a shared tab that stops repainting: a paused video
  const stillAt = useRef(Date.now());  // last time anything on the shared screen changed, even slightly
  const lastLook = useRef<Uint8Array | null>(null);
  const conflicts = useRef(0);
  const lastSpeechAt = useRef(0);  // last voice piece with speech: a still slide with the teacher talking is not a pause
  const conflictRef = useRef<() => Promise<void>>(async () => undefined);
  const [status, setStatus] = useState<{ kind: keyof typeof STATUS_TEXT; msg?: string }>({ kind: initialCapture ? "idle" : "waiting" });
  const [lastNoteId, setLastNoteId] = useState<number | null>(null);
  const [basicMode, setBasicMode] = useState(false); // AI allowance used up: boards get basic notes
  const [quiz, setQuiz] = useState<LiveQuestion | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [quizEvery, setQuizEvery] = useState<"off" | "5" | "10">(() => {
    try { return (localStorage.getItem("focs-quiz-every") as "off" | "5" | "10") || "5"; } catch { return "5"; }
  });
  const [popLoading, setPopLoading] = useState(false);
  const [notifyPerm, setNotifyPerm] = useState<NotificationPermission | "unsupported">(() => ("Notification" in window ? Notification.permission : "unsupported"));
  const askNotifyPermission = () => {
    if (notifyPerm === "default") void Notification.requestPermission().then(setNotifyPerm).catch(() => undefined);
  };
  const lectureSecs = useRef(0);     // seconds of capture while sharing and not paused
  const lastQuizAt = useRef(0);
  const quizRef = useRef<LiveQuestion | null>(null);
  quizRef.current = quiz;
  const pip = usePipWindow();
  const [tab, setTab] = useState<"notes" | "ask">("notes");
  const [focusNote, setFocusNote] = useState<FocusNote | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [now, setNow] = useState(Date.now());
  const inflight = useRef(false);
  const ending = useRef(false);
  const pendingForce = useRef(false);
  const lastSig = useRef<Uint8Array | null>(null);
  const prevPeek = useRef<Uint8Array | null>(null);  // classroom mode: the board must hold still between two looks
  const blankLooks = useRef(0);  // looks in a row at a black tab: its video has gone into picture-in-picture
  const [blank, setBlank] = useState(false);
  const camera = !!capture?.camera;
  const [corners, setCorners] = useState<Corners | null>(null);
  const [cornering, setCornering] = useState(false);
  // classroom mode on a phone: the preview takes the camera's own shape (a phone held upright films a tall picture,
  // which a 16:9 box shrank to a sliver), and "Landscape" goes full screen turned sideways for a wide board
  const [shape, setShape] = useState<number | null>(null);  // width / height of the camera picture
  const [wide, setWide] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const languageWarned = useRef(false);  // the "showing English" notice, once a lecture
  const [captions, setCaptions] = useState<LectureSegment[]>([]);
  const [voice, setVoice] = useState<Voice>("off");
  const chunker = useRef<SpeechChunker | null>(null);
  const audioInflight = useRef(0);  // voice pieces still uploading
  const settleAt = useRef<number | null>(null); // a growing board gets written up once it's still past this time
  const { focus, canFocus, setFocus } = useLectureFocus();
  const [sheet, setSheet] = useState(false);
  const focusRef = useRef(focus);
  focusRef.current = focus;

  const stillSince = mutedAt !== null ? Math.min(stillAt.current, mutedAt) : stillAt.current;
  const pauseStart = voice === "listening" ? Math.max(stillSince, lastSpeechAt.current) : stillSince;
  const looksPaused = sharing && !camera && !paused && !blank && now - pauseStart >= (mutedAt !== null ? 45_000 : 120_000);
  const pauseInfo = () => pausedAt !== null ? { paused: true, secs: (Date.now() - pausedAt) / 1000 }
    : looksPaused ? { paused: true, secs: (Date.now() - pauseStart) / 1000 } : { paused: false, secs: 0 };
  const infoRef = useRef(pauseInfo);
  infoRef.current = pauseInfo;
  const markGone = () => { capture?.stop(); setSharing(false); setGone(true); forgetLive(); };
  const ping = useSessionAlive(session.id, pauseInfo, markGone);
  const conflict = async () => {
    const r = await ping();
    if (r?.active && ++conflicts.current >= 3) markGone();
    lastSig.current = null;
  };
  conflictRef.current = conflict;
  useEffect(() => { rememberLive(session.id); }, [session.id]);

  const { data: detail } = useQuery({ queryKey: ["session", session.id], queryFn: () => api.session(session.id) });
  const notes = [...(detail?.notes ?? [])].reverse();

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => { if (videoRef.current) setVideoEl(videoRef.current); }, []);
  useEffect(() => {
    if (!capture || !videoEl) return;
    capture.attach(videoEl);
    capture.region = region;
    capture.corners = corners;
    capture.onEnded = () => {
      const info = infoRef.current();
      setSharing(false); setStatus({ kind: "waiting" });
      if (capture.camera) toast.message("The camera stopped. Start it again to keep capturing.");
      else setStopped({ secs: info.paused ? info.secs : null });
    };
  }, [capture, videoEl, region, corners]);
  useEffect(() => {
    const track = capture?.stream?.getVideoTracks()[0];
    if (!track || !sharing || capture?.camera) return;
    const mute = () => setMutedAt(Date.now()), unmute = () => setMutedAt(null);
    if (track.muted) mute();
    track.addEventListener("mute", mute);
    track.addEventListener("unmute", unmute);
    return () => { track.removeEventListener("mute", mute); track.removeEventListener("unmute", unmute); setMutedAt(null); };
  }, [capture, sharing]);
  useWakeLock(sharing && !gone);
  useEffect(() => {
    if (!videoEl) return;
    const read = () => { if (videoEl.videoWidth && videoEl.videoHeight) setShape(videoEl.videoWidth / videoEl.videoHeight); };
    read();
    videoEl.addEventListener("loadedmetadata", read);
    videoEl.addEventListener("resize", read);  // the phone was turned: the picture changes shape
    return () => { videoEl.removeEventListener("loadedmetadata", read); videoEl.removeEventListener("resize", read); };
  }, [videoEl]);
  useEffect(() => {
    const left = () => { if (!document.fullscreenElement) setWide(false); };
    document.addEventListener("fullscreenchange", left);
    return () => document.removeEventListener("fullscreenchange", left);
  }, []);
  const orient = async (v: "portrait" | "landscape") => {
    type Lockable = ScreenOrientation & { lock?: (o: string) => Promise<void> };
    const o = screen.orientation as Lockable | undefined;
    if (v === "portrait") {
      try { o?.unlock(); } catch { /* not locked */ }
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined);
      setWide(false);
      return;
    }
    setWide(true);
    try {
      await stageRef.current?.requestFullscreen?.();
      await o?.lock?.("landscape");
    } catch {
      toast.message("Turn your phone sideways (switch rotation lock off) to film the board in landscape.");
    }
  };
  // a newly started camera asks for the board's corners first
  useEffect(() => { if (camera && sharing && !corners) setCornering(true); }, [camera, sharing, corners]);
  // Stop sharing when the studio really unmounts. The deferred check survives React StrictMode's
  // dev-only mount→unmount→mount cycle, which would otherwise kill the stream instantly.
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => () => { const c = capture; setTimeout(() => { if (!mounted.current) c?.stop(); }, 0); }, [capture]);
  useEffect(() => {
    if (!sharing) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [sharing]);

  // the voice lane: the shared tab's sound becomes captions here and "What the teacher said" in the notes
  useEffect(() => {
    if (!capture || !sharing) return;
    const track = capture.audioTrack;
    if (!track || !SpeechChunker.supported()) { setVoice("no_audio"); return; }
    const started = session.started_at ? new Date(session.started_at).getTime() : Date.now();
    const c = new SpeechChunker(track, ({ blob, startS, endS }) => {
      audioInflight.current++;
      lastSpeechAt.current = Date.now();
      api.sendAudio(session.id, blob, startS, endS).finally(() => { audioInflight.current--; }).then((r) => {
        conflicts.current = 0;
        if (r.segment) lastSpeechAt.current = Date.now();
        if (r.segment) { setVoice("listening"); setCaptions((cur) => [...cur.slice(-2), r.segment!]); qc.invalidateQueries({ queryKey: ["session", session.id] }); }
        if (r.skipped === "unavailable") { setVoice("unavailable"); c.stop(); }
        if (r.skipped === "allowance") setVoice("allowance");
        if (r.skipped === "captions") { setVoice("captions"); c.stop(); }
      }).catch((e) => { if (e instanceof ApiError && e.status === 409) void conflictRef.current(); });
    }, () => (Date.now() - started) / 1000);
    chunker.current = c;
    setVoice("listening");
    c.start();
    return () => { c.stop(); chunker.current = null; };
  }, [capture, sharing, session.id, session.started_at, qc]);
  useEffect(() => { if (paused) chunker.current?.pause(); else chunker.current?.resume(); }, [paused]);

  const shareAgain = async () => {
    const c = new LectureCapture(videoRef.current ?? undefined);
    try {
      if (capture?.camera) await c.startCamera(); else await c.start();
      capture?.stop();
      lastSig.current = null;
      lastLook.current = null;
      stillAt.current = Date.now();
      conflicts.current = 0;
      setStopped(null);
      setCapture(c);
      setSharing(true);
      setStatus({ kind: "idle" });
    } catch (e) {
      toast.error(shareFailure(e, !!capture?.camera));
    }
  };

  /* -------- quizzes: topic-change checkpoints + timed pop quizzes, visible even while you watch another tab */
  const showQuiz = useCallback((q: LiveQuestion) => {
    setPicked(null);
    setQuiz(q);
    lastQuizAt.current = lectureSecs.current;
    if (document.hidden && !pip.isOpen && "Notification" in window && Notification.permission === "granted") {
      const plain = q.question.replace(/\$+/g, "").replace(/\\[a-zA-Z]+/g, "").replace(/[{}]/g, "").slice(0, 140);
      const n = new Notification(q.kind === "pop" ? "Pop quiz from Focs" : "Checkpoint from Focs", { body: plain, tag: "focs-quiz" });
      n.onclick = () => { window.focus(); n.close(); };
    }
  }, [pip.isOpen]);

  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const answerQuiz = (i: number, c: Confidence) => {
    if (!quiz || picked !== null) return;
    setPicked(i);
    setConfidence(c);
    api.attempt({ question: quiz.question, q_type: quiz.kind, correct: i === quiz.answer_index, topic: quiz.topic,
      subject: session.subject ?? "", session_id: session.id, confidence: c }).catch(() => undefined);
  };
  const closeQuiz = () => {
    setQuiz(null);
    setPicked(null);
    lastQuizAt.current = lectureSecs.current; // next quiz is a full interval after this one is done
  };

  const quizEveryRef = useRef(quizEvery);
  quizEveryRef.current = quizEvery;
  const popLoadingRef = useRef(false);
  const popQuiz = useCallback(async (manual = false) => {
    if (popLoadingRef.current) return;
    popLoadingRef.current = true;
    setPopLoading(true);
    try {
      const q = await api.sessionPopQuiz(session.id);
      if (mounted.current && !quizRef.current) showQuiz({ ...q, kind: "pop" });
    } catch (e) {
      // automatic quiz failed (AI busy): try again in a minute instead of waiting a whole interval
      lastQuizAt.current = lectureSecs.current - Math.max(0, Number(quizEveryRef.current) * 60 - 60);
      if (manual) toast.message(e instanceof Error ? e.message : "Couldn't write a question right now.");
    } finally {
      popLoadingRef.current = false;
      setPopLoading(false);
    }
  }, [session.id, showQuiz]);

  const changeQuizEvery = (v: "off" | "5" | "10") => {
    setQuizEvery(v);
    lastQuizAt.current = lectureSecs.current;
    try { localStorage.setItem("focs-quiz-every", v); } catch { /* private mode */ }
    if (v !== "off") askNotifyPermission();
  };

  const notesCount = detail?.notes.length ?? 0;
  const unseen = useUnseen(notesCount, sheet || !focus);
  useFocus("lecture", sharing && !paused); // counts while you watch in the other tab
  useEffect(() => {
    // Count real elapsed time, not ticks: browsers slow timers down in background tabs,
    // which is exactly where Focs sits while the student watches the lecture.
    let last = Date.now();
    return steadyInterval(() => {
      const now = Date.now(), dt = (now - last) / 1000;
      last = now;
      if (!sharing || paused) return;
      lectureSecs.current += Math.min(dt, 120); // a sleeping laptop isn't lecture time
      const due = quizEvery !== "off" && lectureSecs.current - lastQuizAt.current >= Number(quizEvery) * 60;
      if (due && notesCount > 0 && !quizRef.current && !ending.current) void popQuiz();
    }, 1000);
  }, [sharing, paused, quizEvery, notesCount, popQuiz]);
  const nextQuizIn = quizEvery === "off" || !notesCount ? null : Math.max(0, Number(quizEvery) * 60 - (lectureSecs.current - lastQuizAt.current));

  const tick = useCallback(async (force = false) => {
    if (!capture?.active) {
      if (force) toast.message("Share your lecture tab first.");
      return;
    }
    if (inflight.current) {
      if (force && !pendingForce.current) {
        pendingForce.current = true; // run right after the board being read now
        toast.message("Capturing right after the current board…");
      }
      return;
    }
    if ((paused && !force) || ending.current) return;
    const track = capture.stream?.getVideoTracks()[0];
    if (!capture.camera && track && (track.muted || track.readyState !== "live")) return;  // nothing new to draw: the last good frame stays
    const sig = capture.peek();
    if (!capture.camera && sig && (!lastLook.current || boardChanged(sig, lastLook.current, 3, 0.001))) { stillAt.current = Date.now(); lastLook.current = sig; }
    if (!capture.camera) {
      // a black tab has nothing to read: don't send it, and after two looks say why it's black
      blankLooks.current = looksBlank(sig) ? blankLooks.current + 1 : 0;
      setBlank(blankLooks.current >= 2);
      if (blankLooks.current > 0 && !force) return;
    }
    if (capture.camera && !force) {
      // a phone on a desk: skip frames while it moves or someone walks past; read the board once it holds still
      const steady = !!prevPeek.current && !boardChanged(sig, prevPeek.current, 22, 0.02);
      prevPeek.current = sig;
      if (!steady) { setStatus((s) => (["created", "updated", "growing"].includes(s.kind) ? s : { kind: "steadying" })); return; }
    }
    const unchanged = !force && !!lastSig.current
      && !(capture.camera ? boardChanged(sig, lastSig.current, 22, 0.01) : boardChanged(sig, lastSig.current));
    const settle = unchanged && settleAt.current !== null && Date.now() >= settleAt.current;
    if (unchanged && !settle) {
      setStatus((s) => (["created", "updated", "growing"].includes(s.kind) ? s : { kind: "unchanged" }));
      return;
    }
    const grab = settle ? null : await capture.grab(slowConnection() ? 0.72 : undefined);  // smaller frames on a slow link
    if (!settle && !grab) return;
    inflight.current = true;
    setStatus({ kind: "reading" });
    try {
      // the teacher stopped writing: one write-up of the finished board instead of one per new line
      const res = grab ? await api.sendFrame(session.id, grab.blob, force, { corners: grab.corners, camera: capture.camera }) : await api.settleBoard(session.id);
      if (!mounted.current) return; // lecture ended while this board was being read
      conflicts.current = 0;
      if (grab && res.status !== "busy") lastSig.current = grab.signature;
      if (res.status === "growing") settleAt.current = Date.now() + (res.settle_after ?? 20) * 1000;
      else if (res.status !== "busy") settleAt.current = null;
      setStatus({ kind: res.status });
      if (res.language_note && !languageWarned.current) { languageWarned.current = true; toast.info(res.language_note); }
      // the board on screen (res.note), or one the lecture moved on from, written up now (res.also_updated)
      const written = res.note ?? res.also_updated;
      const writtenStatus = res.note ? res.status : res.also_status;
      if (written) {
        setBasicMode(!!res.basic_mode);
        if (res.basic_mode) qc.invalidateQueries({ queryKey: ["usage"] });
        setLastNoteId(written.id);
        qc.invalidateQueries({ queryKey: ["session", session.id] });
        if (writtenStatus === "created" && !ending.current && !focusRef.current) toast.success(`New board: ${written.topic ?? "notes added"}`);
        else if (force && res.status === "updated") toast.success("Notes updated with the new lines");
        if (!session.title && written.topic) setSession((s) => ({ ...s, title: s.title || written.topic }));
      }
      if (res.checkpoint && !quizRef.current && !ending.current) showQuiz({ ...res.checkpoint, kind: "checkpoint" });
      if (force && !res.note) {
        const hint: Partial<Record<FrameStatus, string>> = {
          duplicate: "Already captured — nothing new on the board.",
          unchanged: "Already captured — nothing new on the board.",
          no_text: "No writing found. Try “Crop to board”.",
          not_lecture: "That doesn't look like lecture content.",
          busy: "Still saving the previous board — try again in a moment.",
        };
        toast.message(hint[res.status] ?? "Captured.");
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) { await conflictRef.current(); setStatus({ kind: "idle" }); }
      else setStatus({ kind: "error", msg: e instanceof Error ? e.message : undefined });
    } finally {
      inflight.current = false;
      if (pendingForce.current) {
        pendingForce.current = false;
        setTimeout(() => tickRef.current?.(true), 0);
      }
    }
  }, [capture, paused, session.id, session.title, qc, showQuiz]);
  const tickRef = useRef(tick);
  tickRef.current = tick;

  // Pausing keeps the share alive and freezes the last frame on screen (the preview used to go plain black);
  // if the browser ended the share meanwhile, the same button asks for it again instead of doing nothing.
  const [frozen, setFrozen] = useState<string | null>(null);
  const togglePause = () => {
    if (!paused) {
      try {
        const v = videoRef.current;
        if (v && v.videoWidth) {
          const c = document.createElement("canvas");
          c.width = Math.min(v.videoWidth, 1280);
          c.height = Math.round(c.width * v.videoHeight / v.videoWidth);
          c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
          setFrozen(c.toDataURL("image/jpeg", 0.8));
        }
      } catch { setFrozen(null); }
      setPausedAt(Date.now());
      setPaused(true);
      return;
    }
    const secs = pausedAt !== null ? (Date.now() - pausedAt) / 1000 : 0;
    setFrozen(null);
    setPaused(false);
    setPausedAt(null);
    stillAt.current = Date.now();
    lastLook.current = null;
    void ping({ paused: false, secs });
    const live = capture?.stream?.getVideoTracks()[0]?.readyState === "live";
    if (!live) { setSharing(false); setStopped({ secs: secs >= 60 ? secs : null }); return; }
    void videoRef.current?.play().catch(() => undefined);
  };


  useEffect(() => {
    if (sharing && !region && !capture?.camera) setCropping(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sharing]);

  useEffect(() => {
    if (!sharing) return;
    const first = setTimeout(() => tick(), 800);
    const stop = steadyInterval(() => void tick(), Number(interval) * 1000); // keeps pace while the lecture tab is in front
    return () => { clearTimeout(first); stop(); };
  }, [sharing, interval, tick]);

  const end = useMutation({
    mutationFn: async () => {
      ending.current = true; // no new boards or quizzes from here on
      // the teacher's last words too: stopping the voice lane sends its final piece, which must land before the
      // session ends (sent after, the server turned it away with a 409 and "What the teacher said" lost it)
      chunker.current?.stop();
      await new Promise((r) => setTimeout(r, 400));  // the recorder hands over that piece a moment after stopping
      // a board being read right now still belongs in the revision sheet: give it a few seconds to land
      for (let i = 0; (inflight.current || audioInflight.current) && i < 32; i++) await new Promise((r) => setTimeout(r, 250));
      return api.endSession(session.id);
    },
    onError: () => { ending.current = false; },
    onSuccess: (r) => {
      forgetLive();
      capture?.stop();
      qc.invalidateQueries({ queryKey: ["active-session"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["card-stats"] });
      onEnded(r);
    },
  });

  const rename = useMutation({ mutationFn: (title: string) => api.updateSession(session.id, { title }), onSuccess: (s) => setSession(s) });
  const elapsed = session.started_at ? (now - new Date(session.started_at).getTime()) / 1000 : 0;
  const st = STATUS_TEXT[status.kind];
  const t = useT();
  const stoppedCard = !sharing && !camera && !gone && !!stopped;
  const showCard = gone || stoppedCard;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-bad">
            <span className="live-dot" /> Live · {formatDuration(elapsed)}
          </div>
          {editingTitle ? (
            <input autoFocus defaultValue={session.title ?? ""} onBlur={(e) => { setEditingTitle(false); if (e.target.value.trim()) rename.mutate(e.target.value.trim()); }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="mt-1 w-full max-w-xl rounded-lg border border-accent/40 bg-bg-soft px-2 py-1 text-2xl font-semibold tracking-tight outline-none" />
          ) : (
            <div className="mt-1 flex min-w-0 items-center gap-1.5">
              <h1 onClick={() => setEditingTitle(true)} title="Click to rename" className={cn("cursor-text truncate", focus ? "text-[18px]" : "text-[30px]")}>
                {session.title || "Untitled lecture"}
              </h1>
              <button onClick={() => setEditingTitle(true)} className="shrink-0 rounded-sm p-1.5 text-muted hover:bg-elev-2 hover:text-fg"
                title="Rename lecture" aria-label="Rename lecture"><Pencil className="h-4 w-4" /></button>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="hidden items-center gap-4 rounded-xl border border-line bg-bg-soft px-4 py-2 text-xs sm:flex">
            <span><b className="text-fg">{detail?.notes.length ?? 0}</b> <span className="text-muted">{(detail?.notes.length ?? 0) === 1 ? "board saved" : "boards saved"}</span></span>
          </div>
          {!sharing && paused ? (
            <Button variant="primary" onClick={() => { setPaused(false); setPausedAt(null); setFrozen(null); void shareAgain(); }} icon={<MonitorPlay className="h-4 w-4" />}>{t("Share again")}</Button>
          ) : (
            <Button variant="secondary" onClick={togglePause} disabled={!sharing} icon={paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}>
              {t(paused ? "Resume" : "Pause")}
            </Button>
          )}
          {canFocus && !focus && <FocusButton onClick={() => setFocus(true)} />}
          <Button variant="danger" onClick={() => setConfirmEnd(true)} icon={<CircleStop className="h-4 w-4" />}>{t("End lecture")}</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card className="overflow-hidden">
            <div ref={stageRef} className={cn("relative mx-auto bg-black", !camera || !shape ? (showCard ? "w-full" : "aspect-video w-full") : shape < 1 && !wide ? "h-[72dvh] max-w-full" : "w-full",
              wide && "flex h-full items-center")}
              style={camera && shape && !wide ? { aspectRatio: String(shape) } : undefined}>
              <video ref={videoRef} className={cn("h-full w-full object-contain", showCard && "hidden")} playsInline muted />
              {paused && frozen && <img src={frozen} alt="Last frame before the pause" className="absolute inset-0 h-full w-full bg-black object-contain" />}
              {sharing && !camera && <RegionSelector video={videoEl} region={region} enabled={cropping} onChange={(r) => { setRegion(r); setCropping(false); lastSig.current = null; toast.success("Board region set"); }} />}
              {sharing && camera && <CornerSelector video={videoEl} corners={corners} editing={cornering}
                onDone={(c) => { setCorners(c); setCornering(false); lastSig.current = null; prevPeek.current = null; toast.success("Board corners set: frames are straightened before reading"); }} />}
              {!sharing && !showCard && (
                <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,#1e1e1d,#0a0a0a)] p-6 text-center">
                  <div>
                    {camera ? <Smartphone className="mx-auto h-10 w-10 text-muted" /> : <MonitorPlay className="mx-auto h-10 w-10 text-muted" />}
                    <div className="mt-3 font-medium">Not capturing</div>
                    <p className="mt-1 text-sm text-muted">{camera ? "Start the camera again, pointed at the board, to keep taking notes." : "Share the tab playing your lecture to keep taking notes."}</p>
                    <Button variant="primary" className="mt-4" onClick={shareAgain} icon={camera ? <Camera className="h-4 w-4" /> : <MonitorPlay className="h-4 w-4" />}>{camera ? "Start the camera" : "Share lecture tab"}</Button>
                  </div>
                </div>
              )}
              {stoppedCard && stopped && (
                <StageCard icon={<MonitorPlay className="h-9 w-9" />} title={stopped.back ? "Welcome back" : "The screen share stopped"}
                  tip="Tip: set your laptop's screen to stay on longer, or keep this tab visible beside the lecture."
                  actions={<Button variant="primary" onClick={shareAgain} icon={<MonitorPlay className="h-4 w-4" />}>Share the lecture tab again</Button>}>
                  {stopped.back ? `Focs reopened your lecture${stopped.secs ? ` after ${formatPaused(stopped.secs)}` : ""}. Share the lecture tab again to carry on. Your notes are safe.`
                    : `The screen share stopped${stopped.secs ? ` while the lecture was paused for ${formatPaused(stopped.secs)}` : ""} (your computer's screen probably went to sleep). Your notes are safe.`}
                </StageCard>
              )}
              {gone && (
                <StageCard icon={<CircleStop className="h-9 w-9" />} title="This lecture was ended"
                  actions={<>
                    <Link to={`/app/library/${session.id}`} onClick={onGone}><Button variant="primary">See the notes</Button></Link>
                    <Button variant="secondary" onClick={onGone}>Start a new lecture</Button>
                  </>}>
                  This lecture was ended, so Focs stopped taking notes. Your notes are saved.
                </StageCard>
              )}
              {sharing && (
                <div className="glass absolute left-3 top-3 flex items-center gap-2 rounded-full border border-line px-3 py-1.5 text-xs">
                  <span className={cn("h-2 w-2 rounded-full", paused ? "bg-warn" : status.kind === "reading" ? "bg-accent-2" : "bg-ok")} />
                  <span className={st.tone}>{t(paused ? "Paused" : st.text)}</span>
                </div>
              )}
              {blank && sharing && !camera && !cropping && (
                <div role="alert" className="glass absolute inset-x-3 bottom-3 rounded-xl border border-warn/40 px-4 py-3 text-xs leading-relaxed">
                  <p className="font-semibold text-fg">The lecture video went into picture-in-picture, so the shared tab is black.</p>
                  <p className="mt-1 text-muted">
                    Close the small video window (or press “Back to tab” on it). To stop it happening again, open <b className="text-fg">chrome://settings/content/autoPictureInPicture</b> (Edge: <b className="text-fg">edge://settings/content/autoPictureInPicture</b>) and block the lecture site. Want the lecture and Focs side by side? Use “Float over lecture” below.
                  </p>
                </div>
              )}
              {wide && (
                <div className="absolute right-3 top-3 z-10 flex gap-2">
                  <Button size="sm" variant="secondary" disabled={!sharing} onClick={() => tick(true)} icon={<Camera className="h-3.5 w-3.5" />}>{t("Capture now")}</Button>
                  <Button size="sm" variant="secondary" onClick={() => void orient("portrait")}>{t("Exit full screen")}</Button>
                </div>
              )}
              {cropping && (
                <div className="glass absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full border border-line px-4 py-2 text-xs">
                  <Crosshair className="h-3.5 w-3.5 text-accent-2" />
                  <span>Drag a box around the <b>board</b> — skips the teacher and subtitles</span>
                  <button className="font-medium text-muted hover:text-fg" onClick={() => setCropping(false)}>Skip</button>
                </div>
              )}
            </div>
            {sharing && paused && pausedAt !== null && <PauseNotice since={pausedAt} body="Your session stays open. Press Resume to carry on." action={{ label: "Resume", onClick: togglePause }} />}
            {looksPaused && <PauseNotice looks since={pauseStart} />}
            <div className="flex flex-wrap items-center gap-2 border-t border-line p-3">
              <Segmented size="sm" value={interval} onChange={setIntervalSec} options={[
                { value: "3", label: "3s" }, { value: "5", label: "5s" }, { value: "8", label: "8s" },
              ]} />
              {camera && (
                <Segmented size="sm" value={wide ? "landscape" : "portrait"} onChange={(v) => void orient(v)} options={[
                  { value: "portrait", label: t("Portrait") }, { value: "landscape", label: t("Landscape") },
                ]} />
              )}
              {camera ? (
                <Button size="sm" variant={cornering ? "primary" : "secondary"} disabled={!sharing} onClick={() => setCornering(!cornering)} icon={<Crosshair className="h-3.5 w-3.5" />}>
                  {t(cornering ? "Cancel" : corners ? "Re-mark board corners" : "Mark board corners")}
                </Button>
              ) : (
                <>
                  <Button size="sm" variant={cropping ? "primary" : "secondary"} disabled={!sharing} onClick={() => setCropping(!cropping)} icon={<Crosshair className="h-3.5 w-3.5" />}>
                    {t(cropping ? "Cancel crop" : region ? "Re-crop board" : "Crop to board")}
                  </Button>
                  {region && <Button size="sm" variant="ghost" onClick={() => { setRegion(null); lastSig.current = null; }}>Full frame</Button>}
                </>
              )}
              <div className="flex-1" />
              <Button size="sm" variant="ghost" onClick={onPhoto} icon={<ImageIcon className="h-3.5 w-3.5" />}>Add photo</Button>
              <Button size="sm" variant="secondary" disabled={!sharing} onClick={() => tick(true)} icon={<Camera className="h-3.5 w-3.5" />}>{t("Capture now")}</Button>
            </div>
            <CaptionsStrip voice={voice} captions={captions} onShareAgain={shareAgain} />
            {focus && (
              <div className="border-t border-line pt-2">
                <FocusBar notes={notesCount} unseen={unseen} onNotes={() => { setTab("notes"); setSheet(true); }} onAsk={() => { setTab("ask"); setSheet(true); }}
                  onQuiz={() => void popQuiz(true)} quizLoading={popLoading} quizDisabled={!notesCount} onExit={() => setFocus(false)} />
              </div>
            )}
          </Card>

          {!focus && <Card className="p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><Target className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1 basis-48">
                <div className="text-sm font-semibold">Pop quizzes</div>
                <div className="text-xs text-muted">
                  {!notesCount ? "Start after the first board is captured"
                    : quizEvery === "off" ? "Off — tap “Quiz me now” whenever you like"
                    : !sharing ? "Waiting for your lecture tab"
                    : paused ? "Paused with the lecture"
                    : popLoading ? "Writing a question…"
                    : `Next one in ${formatDuration(nextQuizIn ?? 0)}`}
                </div>
              </div>
              <Segmented size="sm" value={quizEvery} onChange={changeQuizEvery} options={[
                { value: "off", label: "Off" }, { value: "5", label: "Every 5 min" }, { value: "10", label: "Every 10 min" },
              ]} />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="sm" variant="secondary" onClick={() => void popQuiz(true)} loading={popLoading} disabled={!notesCount}
                icon={<Target className="h-3.5 w-3.5" />}>Quiz me now</Button>
              {pip.supported && (
                <Button size="sm" variant={pip.isOpen ? "primary" : "secondary"} icon={<PictureInPicture2 className="h-3.5 w-3.5" />}
                  onClick={() => (pip.isOpen ? pip.close() : pip.open().catch(() => toast.message("Couldn't open the floating window.")))}>
                  {pip.isOpen ? "Close floating window" : "Float over lecture"}
                </Button>
              )}
              {notifyPerm === "default" && !pip.isOpen && (
                <Button size="sm" variant="ghost" icon={<Bell className="h-3.5 w-3.5" />}
                  onClick={() => Notification.requestPermission().then(setNotifyPerm).catch(() => undefined)}>Alert me on the lecture tab</Button>
              )}
            </div>
            {!pip.isOpen && (
              <p className="mt-2.5 text-xs leading-relaxed text-muted">
                Watching in another tab? {pip.supported ? "“Float over lecture” keeps a small Focs window on top, so quizzes pop up right over the video." : "Allow alerts and Focs will ping you when a quiz is ready."}
              </p>
            )}
          </Card>}

        </div>

        <NotesSheet focus={focus} open={sheet} onClose={() => setSheet(false)} className="contents">
        <Card className={cn("flex flex-col overflow-hidden", focus ? "min-h-0 flex-1 rounded-none border-0" : "h-[calc(100dvh-190px)] min-h-[560px] xl:sticky xl:top-4")}>
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <Segmented value={tab} onChange={setTab} options={[
              { value: "notes", label: `Notes${detail?.notes.length ? ` · ${detail.notes.length}` : ""}`, icon: <Sparkles className="h-3.5 w-3.5" /> },
              { value: "ask", label: "Ask a doubt", icon: <MessageCircleQuestion className="h-3.5 w-3.5" /> },
            ]} />
          </div>
          {basicMode && <BasicModeBar />}
          <div className={cn("min-h-0 flex-1 space-y-3 overflow-y-auto bg-bg-soft/40 p-4", tab !== "notes" && "hidden")}>
            {!detail && <><Skeleton className="h-40" /><Skeleton className="h-40" /></>}
            {detail && notes.length === 0 && (
              <EmptyState icon={<Lightbulb className="h-6 w-6" />} title="Your notes will appear here"
                body="As soon as the teacher writes something new, Focs turns it into clean notes — no copying needed." />
            )}
            {/* screen readers hear each new board as it's written, without moving their place on the page */}
            <div className="sr-only-live" aria-live="polite">{(() => { const n = notes.find((x) => x.id === lastNoteId); return n ? `New note: ${n.topic ?? "board"}` : ""; })()}</div>
            <AnimatePresence initial={false}>
              {notes.map((n, i) => <NoteCard key={n.id} note={n} index={notes.length - i} onZoom={setZoom} highlight={n.id === lastNoteId}
                onAsk={(note) => { setFocusNote({ id: note.id, topic: note.topic }); setTab("ask"); }} />)}
            </AnimatePresence>
          </div>
          <Companion sessionId={session.id} focus={focusNote} onClearFocus={() => setFocusNote(null)} className={cn("min-h-0 flex-1", tab !== "ask" && "hidden")} />
        </Card>
        </NotesSheet>
      </div>

      <LiveQuizDialog q={quiz} picked={picked} onPick={answerQuiz} onClose={closeQuiz} sessionId={session.id} subject={session.subject} confidence={confidence} />
      {pip.portal(
        <MiniPanel elapsed={elapsed} status={st.text} statusTone={st.tone} notesCount={notesCount} lastTopic={notes[0]?.topic}
          quiz={quiz} picked={picked} onPick={answerQuiz} onDismissQuiz={closeQuiz} nextQuizIn={notesCount ? nextQuizIn : null}
          onQuizNow={() => void popQuiz(true)} quizLoading={popLoading} onCapture={() => void tick(true)} paused={paused}
          caption={voice === "listening" ? captions[captions.length - 1]?.text : null} confidence={confidence} />,
      )}
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
      <Dialog open={confirmEnd} onClose={() => !end.isPending && setConfirmEnd(false)} title="End this lecture?"
        subtitle="Focs will write a revision sheet and add flashcards from everything captured.">
        {end.isPending ? (
          <div className="space-y-3 py-2">
            <div className="flex items-center gap-2 text-sm text-fg-soft"><Sparkles className="h-4 w-4 animate-pulse text-accent" />Writing your revision sheet…</div>
            <Skeleton className="h-3 w-4/5" /><Skeleton className="h-3 w-3/5" /><Skeleton className="h-3 w-2/3" />
          </div>
        ) : (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmEnd(false)}>Keep watching</Button>
            <Button variant="primary" onClick={() => end.mutate()}>End & summarise</Button>
          </div>
        )}
      </Dialog>
    </div>
  );
}

/* ================================================================== summary */
function SummaryView({ result, onNew }: { result: SessionEnd; onNew: () => void }) {
  const s = result.session;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="panel noise relative overflow-hidden p-7 text-center">
        <div className="relative">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-ok/15 text-ok"><Check className="h-7 w-7" /></div>
          <h1 className="mt-4 text-[30px]">{s.title || "Lecture complete"}</h1>
          <p className="mt-1 text-sm text-muted">{s.note_count} boards · {Math.round(s.duration_min)} min · {result.flashcards_created} new flashcards</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Link to={`/app/practice?session=${s.id}`}><Button variant="primary" icon={<Target className="h-4 w-4" />}>Practice this lecture</Button></Link>
            {result.flashcards_created > 0 && <Link to="/app/flashcards"><Button variant="secondary" icon={<Layers className="h-4 w-4" />}>Review cards</Button></Link>}
            <Link to={`/app/library/${s.id}`}><Button variant="secondary">Open notes</Button></Link>
            <Button variant="ghost" onClick={onNew}>New lecture</Button>
          </div>
        </div>
      </motion.div>
      {result.calibration && <CalibrationCard c={result.calibration} title="Where to start" subtitle="This lecture's quizzes: how sure you were, against what you got right" />}
      {result.summary_md ? (
        <RevisionSheet markdown={result.summary_md} title={s.title} meta={`${s.subject || "General"} · ${s.note_count} boards · ${Math.round(s.duration_min)} min`} />
      ) : (
        <Card className="p-6 text-center text-sm text-muted">No boards were captured in this lecture, so there's nothing to summarise.</Card>
      )}
    </div>
  );
}

/* ================================================================== page */
export default function Studio() {
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const { data: active, isLoading } = useQuery({ queryKey: ["active-session"], queryFn: api.activeSession });
  const [live, setLive] = useState<{ session: StudySession; capture: LectureCapture | null } | null>(null);
  const [ended, setEnded] = useState<SessionEnd | null>(null);
  const [back, setBack] = useState<number | null>(null);
  const tried = useRef(false);
  const photoOpen = params.get("mode") === "photo";
  const setPhoto = (open: boolean) => setParams(open ? { mode: "photo" } : {}, { replace: true });

  useEffect(() => {
    if (!live && active && !ended) setLive({ session: active, capture: null });
  }, [active, live, ended]);

  // the browser may have discarded this tab during a long pause: bring the same lecture back if the server allows
  useEffect(() => {
    if (isLoading || active || live || ended || tried.current) return;
    tried.current = true;
    const id = recallLive();
    if (!id) return;
    api.sessionAlive(id, { paused: false, paused_for_s: 0 }).then((r) => {
      if (!r.active) { forgetLive(); return; }
      setBack(r.paused_for_s);
      if (r.reopened) welcomeBack(r.paused_for_s);
      qc.invalidateQueries({ queryKey: ["active-session"] });
    }).catch(() => undefined);
  }, [isLoading, active, live, ended, qc]);
  const lectureGone = () => { forgetLive(); qc.setQueryData(["active-session"], null); setLive(null); };

  let body;
  if (isLoading) body = <div className="space-y-4"><Skeleton className="h-16" /><Skeleton className="aspect-video" /></div>;
  else if (ended) body = <SummaryView result={ended} onNew={() => { setEnded(null); setLive(null); }} />;
  else if (live?.session.source === "link") body = (
    <LinkStudio key={live.session.id} session={live.session} onGone={lectureGone}
      onEnded={(r) => { setEnded(r); setLive(null); qc.setQueryData(["active-session"], null); }} />
  );
  else if (live) body = (
    <LiveStudio key={live.session.id} session={live.session} capture={live.capture} onPhoto={() => setPhoto(true)} onGone={lectureGone} backAfter={live.capture ? null : back}
      onEnded={(r) => { setEnded(r); setLive(null); qc.setQueryData(["active-session"], null); }} />
  );
  else body = (
    <StartScreen onPhoto={() => setPhoto(true)} onStarted={(session, capture) => {
      qc.setQueryData(["active-session"], session);
      setLive({ session, capture });
    }} />
  );

  return (
    <>
      {body}
      <PhotoDialog open={photoOpen} onClose={() => setPhoto(false)} sessionId={live?.session.id} />
    </>
  );
}
