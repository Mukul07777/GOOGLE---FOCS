import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Input, Label, Select, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorCard, MentorWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** A choice chip (topics, languages). */
export function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on}
      className={cn("rounded-sm border px-3 py-1.5 text-[12.5px] transition", on ? "border-fg bg-fg text-bg" : "border-line-strong bg-panel text-fg-soft hover:border-fg")}>
      {children}
    </button>
  );
}

/** A mentor's application: what they cleared, their education, where they are now, their experience, their price, how
    Focs can reach them and proof. Also used to resend a waiting application, or apply again after a rejection. */
export function MentorApplyForm({ ws, profile, onDone }: { ws: MentorWorkspace; profile: MentorCard | null; onDone?: () => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [f, setF] = useState({
    exam: profile?.exam ?? "jee", credential: profile?.credential ?? "", institution: profile?.institution ?? "",
    qualification: profile?.qualification ?? "", experience: profile?.experience ?? "", phone: profile?.phone ?? "",
    headline: profile?.headline ?? "", about: profile?.about ?? "", capacity: profile?.capacity ?? 5,
    call_price_inr: String(profile?.price_set ? profile.call_price_inr : ws.default_call_price_inr),
  });
  const [topics, setTopics] = useState<string[]>(profile?.topics ?? ["plan", "mocks"]);
  const [langs, setLangs] = useState<string[]>(profile?.languages?.length ? profile.languages : ["en"]);
  const [proof, setProof] = useState<File | null>(null);
  const [agree, setAgree] = useState(false);
  const keepsProof = profile?.status === "pending" && profile.has_proof;  // a waiting application keeps the proof already sent
  const toggle = (list: string[], set: (v: string[]) => void, k: string) => set(list.includes(k) ? list.filter((x) => x !== k) : [...list, k]);
  const price = Number(f.call_price_inr);
  const priceOk = f.call_price_inr !== "" && Number.isInteger(price) && price >= 0 && price <= ws.max_call_price_inr;
  const apply = useMutation({
    mutationFn: () => api.mentorApply({ ...f, call_price_inr: price, topics: topics.join(","), languages: langs.join(",") }, proof),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-me"] }); toast.success("Sent. Focs will check it and tell you here."); onDone?.(); },
    onError: failed,
  });
  const ok = f.credential.trim().length >= 6 && f.institution.trim().length >= 2 && f.qualification.trim().length >= 2
    && f.phone.replace(/\D/g, "").length >= 10 && priceOk && (proof || keepsProof) && agree;
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <Card>
      <CardHeader title={profile ? "Your application" : "Apply to mentor"} icon={<Send className="h-4 w-4" />}
        subtitle="Focs checks every mentor by hand. Only Focs staff see your proof and phone number; the proof is deleted once it's reviewed." />
      <div className="space-y-6 p-5">
        <section className="space-y-3">
          <div className="caps text-[10.5px] font-semibold text-muted">1 · What you cleared</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><Label htmlFor="ma-exam">I'll mentor for</Label>
              <Select id="ma-exam" value={f.exam} onChange={set("exam")}>{Object.entries(ws.exams).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></div>
            <div><Label htmlFor="ma-cred">Exam, year and rank</Label><Input id="ma-cred" value={f.credential} onChange={set("credential")} maxLength={160} placeholder="e.g. JEE Advanced 2023, AIR 1,204" /></div>
            <div><Label htmlFor="ma-qual">Highest qualification</Label><Input id="ma-qual" value={f.qualification} onChange={set("qualification")} maxLength={160} placeholder="e.g. B.Tech CSE, IIT Delhi (2026)" /></div>
            <div><Label htmlFor="ma-inst">Where you are now</Label><Input id="ma-inst" value={f.institution} onChange={set("institution")} maxLength={80} placeholder="e.g. IIT Delhi, 3rd year · or a company" /></div>
          </div>
          <div><Label htmlFor="ma-exp" hint="optional">Teaching or mentoring you've done</Label>
            <Textarea id="ma-exp" rows={2} value={f.experience} onChange={set("experience")} maxLength={2000} placeholder="e.g. Taught maths to Class 11 students at a coaching centre for a year." /></div>
        </section>

        <section className="space-y-3">
          <div className="caps text-[10.5px] font-semibold text-muted">2 · What students see</div>
          <div><Label htmlFor="ma-head">One line about you</Label><Input id="ma-head" value={f.headline} onChange={set("headline")} maxLength={120} placeholder="e.g. Went from 90 to 210 in mocks in five months" /></div>
          <div><Label htmlFor="ma-about">How you can help</Label>
            <Textarea id="ma-about" rows={3} value={f.about} onChange={set("about")} maxLength={2000} placeholder="Your story, what worked for you, and the kind of student you'd help best." /></div>
          <div><Label>Topics</Label>
            <div className="flex flex-wrap gap-1.5">{Object.entries(ws.topics).map(([k, v]) => <Chip key={k} on={topics.includes(k)} onClick={() => toggle(topics, setTopics, k)}>{v}</Chip>)}</div></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><Label>Languages</Label>
              <div className="flex flex-wrap gap-1.5">{Object.entries(ws.languages).map(([k, v]) => <Chip key={k} on={langs.includes(k)} onClick={() => toggle(langs, setLangs, k)}>{v}</Chip>)}</div></div>
            <div><Label htmlFor="ma-cap">Students at once</Label>
              <Select id="ma-cap" value={String(f.capacity)} onChange={(e) => setF({ ...f, capacity: Number(e.target.value) })}>
                {[1, 2, 3, 5, 8, 10, 15, 20].filter((n) => n <= ws.max_capacity).map((n) => <option key={n}>{n}</option>)}</Select></div>
          </div>
        </section>

        <section className="space-y-3">
          <div className="caps text-[10.5px] font-semibold text-muted">3 · Your price and contact</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="ma-price" hint={`₹0 to ₹${ws.max_call_price_inr}`}>Price for a {ws.call_minutes}-minute private call (₹)</Label>
              <Input id="ma-price" inputMode="numeric" value={f.call_price_inr} onChange={(e) => setF({ ...f, call_price_inr: e.target.value.replace(/\D/g, "") })} />
              <p className="mt-1 text-[11.5px] text-muted">{priceOk ? (price ? `You earn ₹${price - Math.round((price * ws.commission_pct) / 100)} of each call (Focs keeps ${ws.commission_pct}%).` : "Free calls: students book without paying.") : "Enter a whole number in range."} You set master-session prices when you post each one.</p>
            </div>
            <div><Label htmlFor="ma-phone" hint="never shown to students">Phone number</Label>
              <Input id="ma-phone" inputMode="tel" value={f.phone} onChange={set("phone")} maxLength={20} placeholder="+91 98765 43210" /></div>
          </div>
          <div>
            <Label hint={keepsProof ? "already sent: add a new file only to replace it" : "only Focs staff see it"}>Proof of what you cleared</Label>
            <button type="button" onClick={() => input.current?.click()}
              className="flex w-full items-center gap-3 rounded-sm border border-dashed border-line-strong bg-panel p-4 text-left transition hover:border-fg">
              <Upload className="h-5 w-5 shrink-0" />
              <span className="min-w-0 flex-1 text-sm">{proof ? <span className="block truncate font-medium">{proof.name}</span>
                : <>Rank card, scorecard, degree or college ID <span className="text-muted">· PDF or photo, up to 8 MB</span></>}</span>
            </button>
            <input ref={input} type="file" accept="application/pdf,image/*" hidden onChange={(e) => setProof(e.target.files?.[0] ?? null)} />
          </div>
        </section>

        <label className="flex items-start gap-2.5 rounded-sm border border-line bg-bg-soft p-3 text-[13px]">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 accent-[var(--accent)]" />
          <span>I'll keep conversations on Focs, never ask a student for money outside Focs, photos or their phone number, and reply to my students every week. Many students are under 18.</span>
        </label>
        <Button variant="primary" size="lg" className="w-full" disabled={!ok} loading={apply.isPending} onClick={() => apply.mutate()}>
          {profile ? "Send for review again" : "Send for review"}
        </Button>
      </div>
    </Card>
  );
}
