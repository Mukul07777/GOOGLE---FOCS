import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Hash, MessageCircleQuestion, PlayCircle, Sparkles, Target, Users } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState, Input, Label } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

export default function Rooms() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", video_url: "", topic: "" });
  const [code, setCode] = useState("");
  const { data: rooms } = useQuery({ queryKey: ["rooms"], queryFn: api.myRooms });
  const create = useMutation({
    mutationFn: () => api.createRoom({ name: form.name.trim(), video_url: form.video_url.trim(), topic: form.topic.trim() }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["rooms"] }); navigate(`/app/rooms/${r.code}`); },
  });
  const join = useMutation({ mutationFn: () => api.joinRoom(code), onSuccess: (r) => navigate(`/app/rooms/${r.code}`) });

  return (
    <div>
      <PageHeader title="Study rooms" subtitle="Watch a lecture together, discuss doubts, and let Focs quiz the whole room on what was just taught." />
      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          [PlayCircle, "Watch in sync", "Paste a YouTube lecture — it plays, pauses and seeks together for everyone."],
          [Target, "Pop quizzes", "Focs pauses the video and asks the room a question on the last few minutes."],
          [MessageCircleQuestion, "Doubts & Ask AI", "Raise a doubt for the group or ask Focs — everyone sees the answer."],
        ].map(([Icon, t, b]) => {
          const I = Icon as typeof PlayCircle;
          return (
            <div key={String(t)} className="rounded-2xl border border-line bg-bg-soft p-4">
              <I className="h-4 w-4 text-accent" />
              <div className="mt-2 text-sm font-medium">{String(t)}</div>
              <div className="mt-1 text-xs leading-relaxed text-muted">{String(b)}</div>
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.3fr_1fr]">
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-brand text-brand-fg"><Sparkles className="h-5 w-5" /></div>
            <div>
              <h2 className="font-semibold">Start a lecture room</h2>
              <p className="text-[13px] text-muted">You'll get a 6-character code to share with friends.</p>
            </div>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="mt-5 space-y-3">
            <div><Label htmlFor="room-name">Room name</Label><Input id="room-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Evening revision group" maxLength={60} required /></div>
            <div><Label hint="optional — add it later too">YouTube lecture link</Label><Input value={form.video_url} onChange={(e) => setForm({ ...form, video_url: e.target.value })} placeholder="https://youtu.be/…" /></div>
            <div><Label hint="helps Focs ask better questions">Topic</Label><Input value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} placeholder="Rotational motion — torque & angular momentum" maxLength={120} /></div>
            <Button type="submit" variant="primary" className="w-full" loading={create.isPending} disabled={!form.name.trim()}>Create room <ArrowRight className="h-4 w-4" /></Button>
            {!form.name.trim() && <p className="text-[12px] text-muted">Name the room to create it.</p>}
          </form>
        </Card>
        <div className="space-y-5">
          <Card className="p-6">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-elev-2 text-accent-2"><Hash className="h-5 w-5" /></div>
            <h2 className="mt-4 font-semibold">Join with a code</h2>
            <form onSubmit={(e) => { e.preventDefault(); join.mutate(); }} className="mt-4 flex gap-2">
              <Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} placeholder="ABC123" maxLength={8}
                className="font-mono tracking-[0.3em] uppercase" />
              <Button type="submit" loading={join.isPending} disabled={code.length < 4}>Join <ArrowRight className="h-4 w-4" /></Button>
            </form>
          </Card>
          <Card>
            <CardHeader title="Your rooms" subtitle="Rooms you host stay open until you close them" />
            <div className="p-3">
              {rooms?.length === 0 && <EmptyState icon={<Users className="h-6 w-6" />} title="No rooms yet" body="Create one and invite your study group." />}
              {rooms?.map((r) => (
                <button key={r.code} onClick={() => navigate(`/app/rooms/${r.code}`)} className="flex w-full items-center gap-4 rounded-xl px-3 py-3 text-left transition hover:bg-elev-2">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-elev-2"><PlayCircle className="h-4 w-4 text-accent" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{r.name}</div>
                    <div className="truncate text-xs text-muted">{r.topic || "No topic"} · {timeAgo(r.created_at)} · {r.online} online</div>
                  </div>
                  <span className="rounded-lg border border-line px-2 py-1 font-mono text-xs tracking-widest">{r.code}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
