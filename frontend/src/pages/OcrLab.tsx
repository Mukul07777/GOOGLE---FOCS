import { useMutation, useQuery } from "@tanstack/react-query";
import { Clipboard, Cpu, FlaskConical, Gauge, ImagePlus, Layers, ScanText, Sparkles, Trophy, Wand2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, ProgressBar, Segmented, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Benchmark, OcrResult } from "@/lib/types";
import { cn } from "@/lib/utils";

type Engine = "auto" | "focs" | "rapid";
const ENGINE_LABEL: Record<string, string> = { auto: "Ensemble", focs: "FocsOCR", rapid: "PP-OCRv4" };
const ENGINE_COLOR: Record<string, string> = { focs: "var(--accent)", rapid: "var(--accent-2)" };

const SAMPLES = {
  chalkboard: { bg: "#1d3a2e", fg: ["#f3f3ea", "#f6e27a", "#f3f3ea", "#9fd3f7", "#f3f3ea"] },
  whiteboard: { bg: "#f4f5f1", fg: ["#1b2a8c", "#1a1a1a", "#b3202a", "#1a1a1a", "#1b7a3a"] },
  "pen tablet": { bg: "#0b0b0e", fg: ["#ffe45c", "#6ee7ff", "#ffffff", "#a3ff7a", "#ff8ad8"] },
};
const SAMPLE_LINES = ["Kinematics — Lecture 3", "v = u + at", "s = ut + ½at²", "v² = u² + 2as", "θ = 30°, g = 9.8 m/s²"];

async function sampleBoard(kind: keyof typeof SAMPLES): Promise<File> {
  const c = document.createElement("canvas");
  c.width = 1280; c.height = 720;
  const ctx = c.getContext("2d")!;
  const s = SAMPLES[kind];
  ctx.fillStyle = s.bg; ctx.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < 1800; i++) { // board texture
    ctx.fillStyle = kind === "whiteboard" ? "rgba(0,0,0,0.015)" : "rgba(255,255,255,0.02)";
    ctx.fillRect(Math.random() * 1280, Math.random() * 720, 2, 2);
  }
  SAMPLE_LINES.forEach((line, i) => {
    ctx.fillStyle = s.fg[i];
    ctx.font = `${i === 0 ? 58 : 52}px "Segoe Print", "Comic Sans MS", cursive`;
    ctx.save();
    ctx.translate(90 + (i % 2) * 12, 120 + i * 118);
    ctx.rotate((Math.random() - 0.5) * 0.025);
    ctx.fillText(line, 0, 0);
    ctx.restore();
  });
  const blob = await new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/jpeg", 0.8));
  return new File([blob], `${kind}.jpg`, { type: "image/jpeg" });
}

/** End-to-end results on one frame set: FocsOCR, PP-OCR and both combined. */
function BenchmarkCard({ bench, title, subtitle }: { bench: Benchmark; title: string; subtitle: string }) {
  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} icon={<Trophy className="h-4 w-4" />} />
      <div className="p-4">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-muted"><th className="pb-2 font-medium">Engine</th><th className="pb-2 font-medium">CER ↓</th><th className="pb-2 font-medium">Line acc ↑</th><th className="pb-2 text-right font-medium">ms / frame</th></tr></thead>
          <tbody>
            {Object.entries(bench.engines).sort((a, b) => a[1].cer - b[1].cer).map(([name, r], i) => (
              <tr key={name} className="border-t border-line">
                <td className="py-2 font-medium">{ENGINE_LABEL[name] ?? name} {i === 0 && <Badge tone="ok" className="ml-1">best</Badge>}</td>
                <td className="py-2">{(r.cer * 100).toFixed(1)}%</td>
                <td className="py-2">{(r.line_acc * 100).toFixed(0)}%</td>
                <td className="py-2 text-right text-muted">{Math.round(r.ms_per_image)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {bench.by_style && (
          <div className="mt-4">
            <div className="mb-2 text-xs font-medium text-muted">CER by board style</div>
            <div className="space-y-2">
              {Object.entries(bench.by_style).map(([style, byEngine]) => (
                <div key={style} className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3 text-xs">
                  <span className="truncate text-fg-soft">{style}</span>
                  <div className="flex flex-wrap gap-x-3 gap-y-1">
                    {Object.entries(byEngine).map(([eng, cer]) => (
                      <span key={eng} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: eng === "auto" ? "var(--ok)" : ENGINE_COLOR[eng] }} />{ENGINE_LABEL[eng] ?? eng} {(cer * 100).toFixed(1)}%</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {bench.licences && (
          <p className="mt-4 text-xs text-muted">
            From {bench.sources ?? 0} openly licensed sources: {Object.entries(bench.licences).map(([l, n]) => `${n} × ${l}`).join(", ")}.
          </p>
        )}
      </div>
    </Card>
  );
}

function ModelCardPanel() {
  const { data, isLoading } = useQuery({ queryKey: ["ocr-model"], queryFn: api.ocrModel });
  if (isLoading) return <Skeleton className="h-[640px]" />;
  const card = data?.model_card;
  const bench = data?.benchmark;
  const curve = (card?.loss_curve ?? []).map((p) => ({ step: p.step, loss: p.loss }));
  const evalCurve = (card?.eval_curve ?? []).map((p) => ({ step: p.step, cer: +(p.cer * 100).toFixed(2), acc: +(p.line_acc * 100).toFixed(1) }));

  return (
    <div className="space-y-4">
      <Card className="noise relative overflow-hidden p-6">
        <div className="relative">
          <div className="flex items-center gap-2">
            <Badge tone="accent"><Sparkles className="h-3 w-3" />Trained in-house</Badge>
            {card && <Badge>v{card.version}</Badge>}
            {data?.detector && <Badge tone="cyan">{data.detector}</Badge>}
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-tight">FocsOCR</h2>
          <p className="mt-1 text-sm text-muted">{card?.architecture ?? "Model not trained yet — run train_ocr.bat."}</p>
          {card && (
            <div className="mt-5 grid grid-cols-3 gap-3">
              {[["CER", `${(card.validation.cer * 100).toFixed(1)}%`, "character error"], ["Line accuracy", `${(card.validation.line_acc * 100).toFixed(0)}%`, "exact lines"], ["WER", `${(card.validation.wer * 100).toFixed(1)}%`, "word error"]].map(([k, v, s]) => (
                <div key={k} className="rounded-xl border border-line bg-bg-soft/80 p-3">
                  <div className="text-2xl font-semibold tracking-tight text-gradient">{v}</div>
                  <div className="text-xs font-medium">{k}</div>
                  <div className="text-[11px] text-muted">{s}</div>
                </div>
              ))}
            </div>
          )}
          {card && (
            <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px]">
              {[
                ["Parameters", `${(card.params / 1e6).toFixed(2)} M`],
                ["Charset", `${card.charset_size} symbols`],
                ["Samples seen", card.training.samples_seen ? `${(card.training.samples_seen / 1e6).toFixed(2)} M` : "—"],
                ["Trained on", card.training.device ?? "—"],
                ["Training time", card.training.train_minutes ? `${card.training.train_minutes} min` : "—"],
                ["Validation set", `${card.validation.n} lines`],
              ].map(([k, v]) => <div key={k} className="flex justify-between gap-2 border-b border-line py-1"><span className="text-muted">{k}</span><span className="truncate font-medium">{v}</span></div>)}
            </div>
          )}
        </div>
      </Card>

      {evalCurve.length > 1 && (
        <Card>
          <CardHeader title="Learning curve" subtitle="Validation character error rate (%) and training loss" icon={<Gauge className="h-4 w-4" />} />
          <div className="grid h-56 grid-cols-2 gap-2 p-4">
            <ResponsiveContainer>
              <LineChart data={evalCurve} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="step" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "var(--elev)", border: "1px solid var(--line-strong)", borderRadius: 12, fontSize: 12 }} />
                <Line dataKey="cer" name="CER %" stroke="var(--accent)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <ResponsiveContainer>
              <LineChart data={curve} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="step" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <YAxis scale="log" domain={["auto", "auto"]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip contentStyle={{ background: "var(--elev)", border: "1px solid var(--line-strong)", borderRadius: 12, fontSize: 12 }} />
                <Line dataKey="loss" name="CTC loss" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {bench && <BenchmarkCard bench={bench} title="Board benchmark" subtitle={`${bench.images} synthetic lecture frames · ${bench.lines} lines · end-to-end`} />}
      {data?.benchmark_real && <BenchmarkCard bench={data.benchmark_real} title="Real boards"
        subtitle={`${data.benchmark_real.images} frames from real lectures and classrooms · ${data.benchmark_real.lines} lines · hand-labelled`} />}

      {card && card.examples.length > 0 && (
        <Card>
          <CardHeader title="Validation samples" subtitle="Ground truth vs FocsOCR prediction" icon={<Layers className="h-4 w-4" />} />
          <div className="divide-y divide-line p-2">
            {card.examples.map((e, i) => (
              <div key={i} className="grid gap-1 px-3 py-2 font-mono text-[12.5px]">
                <div className="text-muted">{e.gt}</div>
                <div className={e.gt === e.pred ? "text-ok" : "text-warn"}>{e.pred || "∅"}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

export default function OcrLab() {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [engine, setEngine] = useState<Engine>("auto");
  const [result, setResult] = useState<OcrResult | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [dims, setDims] = useState({ w: 1, h: 1 });

  const run = useMutation({ mutationFn: ({ f, e }: { f: File; e: Engine }) => api.runOcr(f, e), onSuccess: setResult });

  const load = useCallback((f: File | null | undefined, e: Engine = engine) => {
    if (!f || !f.type.startsWith("image/")) return;
    setFile(f);
    setUrl((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(f); });
    setResult(null);
    run.mutate({ f, e });
  }, [engine, run]);

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? []).find((i) => i.type.startsWith("image/"));
      if (item) load(item.getAsFile());
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [load]);

  return (
    <div>
      <PageHeader title="OCR Lab" eyebrow={<span className="flex items-center gap-1.5"><FlaskConical className="h-3.5 w-3.5" />Under the hood</span>}
        subtitle="See exactly how Focs reads a board. Compare our model with PP-OCRv4 line by line."
        actions={<Segmented value={engine} onChange={(e) => { setEngine(e); if (file) run.mutate({ f: file, e }); }}
          options={[{ value: "auto", label: "Ensemble" }, { value: "focs", label: "FocsOCR" }, { value: "rapid", label: "PP-OCRv4" }]} />} />

      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card className="overflow-hidden">
            {!url ? (
              <label onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); load(e.dataTransfer.files?.[0]); }}
                className="flex aspect-video cursor-pointer flex-col items-center justify-center gap-3 bg-bg-soft text-center transition hover:bg-elev-2">
                <div className="grid h-14 w-14 place-items-center rounded-2xl bg-accent-soft text-accent"><ImagePlus className="h-6 w-6" /></div>
                <div className="text-sm font-medium">Drop a board image, click to choose, or paste <span className="text-muted">(Ctrl+V)</span></div>
                <div className="text-xs text-muted">Screenshots of lectures, slides, photos of whiteboards — anything</div>
                <input type="file" accept="image/*" className="hidden" onChange={(e) => load(e.target.files?.[0])} />
              </label>
            ) : (
              <div className="relative bg-black">
                <img src={url} alt="Input" className="w-full" onLoad={(e) => setDims({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} />
                {result && (
                  <svg viewBox={`0 0 ${result.width || dims.w} ${result.height || dims.h}`} className="absolute inset-0 h-full w-full">
                    {result.lines.map((l, i) => (
                      <polygon key={i} points={l.box.map((p) => p.join(",")).join(" ")} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                        fill={hover === i ? "rgba(139,108,255,0.25)" : "rgba(139,108,255,0.06)"} stroke={ENGINE_COLOR[l.engine] ?? "var(--accent)"}
                        strokeWidth={Math.max(2, (result.width || 1000) / 500)} className="cursor-pointer" />
                    ))}
                  </svg>
                )}
                {run.isPending && <div className="absolute inset-0 overflow-hidden bg-black/30"><div className="scanline" /></div>}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 border-t border-line p-3">
              <span className="mr-1 flex items-center gap-1.5 text-xs text-muted"><Wand2 className="h-3.5 w-3.5" />Try a sample:</span>
              {(Object.keys(SAMPLES) as (keyof typeof SAMPLES)[]).map((k) => (
                <Button key={k} size="sm" variant="secondary" onClick={async () => load(await sampleBoard(k))}>{k}</Button>
              ))}
              <div className="flex-1" />
              {url && <label className="cursor-pointer"><span className="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-[13px] font-medium text-fg-soft hover:bg-elev-2"><Clipboard className="h-3.5 w-3.5" />Another image</span><input type="file" accept="image/*" className="hidden" onChange={(e) => load(e.target.files?.[0])} /></label>}
            </div>
          </Card>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><ScanText className="h-4 w-4 text-accent" />Recognised lines</div>
              {result && (
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge>{result.board}</Badge><Badge tone="cyan"><Cpu className="h-3 w-3" />{result.elapsed_ms} ms on CPU</Badge>
                  <Badge tone="accent">{ENGINE_LABEL[result.engine] ?? result.engine}</Badge>
                </div>
              )}
            </div>
            <div className="p-3">
              {!result && !run.isPending && <EmptyState icon={<ScanText className="h-6 w-6" />} title="Nothing read yet" body="Load an image to see line-by-line recognition with confidence scores." />}
              {run.isPending && <div className="space-y-2 p-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
              {result && result.lines.length === 0 && <p className="p-6 text-center text-sm text-muted">No text detected.</p>}
              {result?.lines.map((l, i) => (
                <div key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                  className={cn("rounded-xl px-3 py-2.5 transition", hover === i && "bg-elev-2")}>
                  <div className="flex items-center gap-3">
                    <span className="min-w-0 flex-1 font-mono text-[14px]">{l.text}</span>
                    <span className="rounded px-1.5 text-[10px] font-semibold uppercase" style={{ color: ENGINE_COLOR[l.engine], background: `color-mix(in oklab, ${ENGINE_COLOR[l.engine] ?? "var(--accent)"} 14%, transparent)` }}>{ENGINE_LABEL[l.engine] ?? l.engine}</span>
                    <span className="w-10 text-right text-xs tabular-nums text-muted">{Math.round(l.confidence * 100)}%</span>
                  </div>
                  {l.candidates && engine === "auto" && (
                    <div className="mt-1.5 grid grid-cols-1 gap-1 sm:grid-cols-2">
                      {Object.entries(l.candidates).map(([eng, c]) => (
                        <div key={eng} className={cn("flex items-center gap-2 rounded-lg border px-2 py-1 text-[11.5px]", eng === l.engine ? "border-line-strong" : "border-transparent opacity-60")}>
                          <span className="w-16 shrink-0 font-medium" style={{ color: ENGINE_COLOR[eng] }}>{ENGINE_LABEL[eng]}</span>
                          <span className="min-w-0 flex-1 truncate font-mono">{c.text || "∅"}</span>
                          <ProgressBar value={c.confidence * 100} className="w-12" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
        <ModelCardPanel />
      </div>
    </div>
  );
}
