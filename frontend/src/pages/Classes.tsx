import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Copy, LogIn, Presentation, ShieldCheck, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");
export const copyText = (text: string, done: string) => navigator.clipboard.writeText(text).then(() => toast.success(done), () => toast.error("Couldn't copy. Select it and copy by hand."));

/** Classes: join your teacher's with a code, or run your own and see how every student is doing. */
export default function Classes() {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["classes"], queryFn: api.classes });
  const refresh = () => qc.invalidateQueries({ queryKey: ["classes"] });
  const join = useMutation({ mutationFn: () => api.joinClass(code), onError: failed,
    onSuccess: (c) => { refresh(); setCode(""); toast.success(`You're in ${c.name}. ${c.teacher} can now see your progress.`); } });
  const create = useMutation({ mutationFn: () => api.createClass(name), onError: failed,
    onSuccess: (c) => { refresh(); setName(""); toast.success(`Class made. Its code is ${c.code}.`); } });
  const leave = useMutation({ mutationFn: (id: number) => api.leaveClass(id), onError: failed, onSuccess: () => { refresh(); toast.success("You left the class"); } });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Presentation className="h-3.5 w-3.5" />Classes</span>}
        title="Your teacher, your class, one view"
        subtitle="Students join with a code. Teachers see who is studying, how far the syllabus has got, and the chapters the class is stuck on." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Join a class" icon={<LogIn className="h-4 w-4" />} subtitle="Enter the code your teacher gave you." />
          <div className="space-y-4 p-5">
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (code.trim().length >= 4) join.mutate(); }}>
              <Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={8} placeholder="Class code" aria-label="Class code"
                className="font-mono tracking-[0.2em]" />
              <Button type="submit" variant="primary" disabled={code.trim().length < 4} loading={join.isPending}>Join</Button>
            </form>
            <p className="flex gap-2 text-xs leading-relaxed text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
              Joining lets that teacher see your study time, syllabus progress, test scores and weak chapters. Never your notes or your doubts. You can leave at any time.</p>
            {isLoading ? <Skeleton className="h-14" /> : data?.joined.map((c) => (
              <div key={c.id} className="flex items-center gap-3 rounded-xl border border-line bg-bg-soft p-3">
                <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{c.name}</div><div className="text-xs text-muted">with {c.teacher}</div></div>
                <Button size="sm" variant="ghost" loading={leave.isPending && leave.variables === c.id} onClick={() => leave.mutate(c.id)}>Leave</Button>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Teach a class" icon={<Users className="h-4 w-4" />} subtitle="A coaching batch, a school section, a study group you mentor." />
          <div className="space-y-4 p-5">
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim().length >= 2) create.mutate(); }}>
              <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="e.g. Physics batch A, 2027" aria-label="Class name" />
              <Button type="submit" variant="primary" disabled={name.trim().length < 2} loading={create.isPending}>Create</Button>
            </form>
            {isLoading ? <Skeleton className="h-14" /> : !data?.teaching.length ? (
              <p className="text-xs leading-relaxed text-muted">Make a class, give its code to your students, and their progress shows up here as they join. Free while Focs is in early access.</p>
            ) : data.teaching.map((c) => (
              <div key={c.id} className="flex items-center gap-3 rounded-xl border border-line bg-bg-soft p-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{c.name}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                    <button type="button" onClick={() => copyText(c.code, "Code copied")} title="Copy the code" className="inline-flex items-center gap-1 hover:text-fg">
                      <Badge tone="accent" className="font-mono tracking-widest">{c.code}</Badge><Copy className="h-3 w-3" /></button>
                    <span>{c.students} student{c.students === 1 ? "" : "s"}</span>
                  </div>
                </div>
                <Link to={`/app/classes/${c.id}`}><Button size="sm" variant="secondary">Open<ArrowRight className="h-3.5 w-3.5" /></Button></Link>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
