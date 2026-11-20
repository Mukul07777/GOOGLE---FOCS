import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Camera, KeyRound, LogOut, Trash2, UserRound } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Chip } from "@/components/MentorApplyForm";
import { useWorkspace } from "@/components/MentorShell";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Card, CardHeader, Input, Label, Select, Skeleton, Switch, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorCard, MentorWorkspace } from "@/lib/types";
import { PriceCard } from "@/pages/mentor/MentorCallsPage";
import { Initials } from "@/pages/Mentors";
import { useAuth } from "@/stores/auth";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** The photo on the card. Focs checks each one before students see it (many of them are under 18): with the
 * application, or on its own once the mentor is listed, while the old photo stays up. */
function PhotoCard({ profile }: { profile: MentorCard }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const listed = profile.status === "approved";
  const refresh = () => qc.invalidateQueries({ queryKey: ["mentor-me"] });
  const upload = useMutation({
    mutationFn: (file: File) => api.mentorPhoto(file),
    onSuccess: () => { refresh(); toast.success(listed ? "Sent. Students see it once Focs has checked it." : "Added to your application."); },
    onError: failed,
  });
  const remove = useMutation({ mutationFn: api.mentorPhotoRemove, onSuccess: () => { refresh(); toast.success("Photo removed"); }, onError: failed });
  const shown = profile.photo_pending ?? profile.photo;
  const state = profile.photo_pending
    ? listed ? `Waiting for Focs to check it. Until then students see ${profile.photo ? "your current photo" : "your initials"}.`
      : "Sent with your application, and checked with it."
    : profile.photo ? "Students see this photo on your card." : "No photo yet: students see your initials.";
  return (
    <Card>
      <CardHeader title="Your photo" icon={<Camera className="h-4 w-4" />} subtitle="Students find it easier to ask someone whose face they can see." />
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <Initials name={profile.name} photo={shown} className="h-20 w-20 text-xl" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{state}</div>
          <p className="mt-1 text-xs text-muted">A clear photo of your face, just you: no logos, text or contact details. It is cropped to a square.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate(file); e.target.value = ""; }} />
          <Button variant="primary" loading={upload.isPending} onClick={() => input.current?.click()}>{shown ? "Change photo" : "Add a photo"}</Button>
          {shown && <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>Remove</Button>}
        </div>
      </div>
    </Card>
  );
}

/** What students see on the mentor's card. What Focs verified stays fixed; the rest is theirs to change any time. */
function PublicProfile({ ws, profile }: { ws: MentorWorkspace; profile: MentorCard }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ headline: profile.headline, about: profile.about, capacity: profile.capacity, accepting: profile.accepting });
  const [topics, setTopics] = useState<string[]>(profile.topics);
  const [langs, setLangs] = useState<string[]>(profile.languages);
  const toggle = (list: string[], set: (v: string[]) => void, k: string) => set(list.includes(k) ? list.filter((x) => x !== k) : [...list, k]);
  const save = useMutation({
    mutationFn: () => api.mentorEdit({ ...f, topics, languages: langs }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-me"] }); toast.success("Saved. Students see it now."); },
    onError: failed,
  });
  const ok = topics.length > 0 && topics.length <= 8 && langs.length > 0 && langs.length <= 2;
  return (
    <Card>
      <CardHeader title="Your card" icon={<UserRound className="h-4 w-4" />} subtitle={`What students preparing for ${profile.exam_label} see when they look for a mentor.`} />
      <div className="space-y-5 p-5">
        <div className="grid gap-px border border-line bg-line sm:grid-cols-3">
          {[["Cleared", profile.credential], ["Qualification", profile.qualification], ["Now at", profile.institution]].map(([k, v]) => (
            <div key={k} className="bg-panel px-4 py-3">
              <div className="caps flex items-center gap-1 text-[10px] text-muted"><BadgeCheck className="h-3 w-3" />{k}</div>
              <div className="mt-1 text-sm font-medium">{v || "—"}</div>
            </div>
          ))}
        </div>
        <p className="-mt-2 text-xs text-muted">Verified by Focs. To change these, write to Focs support with new proof.</p>
        <div><Label htmlFor="mp-head">One line about you</Label>
          <Input id="mp-head" value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} maxLength={120} /></div>
        <div><Label htmlFor="mp-about">How you can help</Label>
          <Textarea id="mp-about" rows={4} value={f.about} onChange={(e) => setF({ ...f, about: e.target.value })} maxLength={2000} /></div>
        <div><Label hint="up to 8">I can help with</Label>
          <div className="flex flex-wrap gap-1.5">{Object.entries(ws.topics).map(([k, v]) => <Chip key={k} on={topics.includes(k)} onClick={() => toggle(topics, setTopics, k)}>{v}</Chip>)}</div></div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div><Label hint="up to 2">Languages</Label>
            <div className="flex flex-wrap gap-1.5">{Object.entries(ws.languages).map(([k, v]) => <Chip key={k} on={langs.includes(k)} onClick={() => toggle(langs, setLangs, k)}>{v}</Chip>)}</div></div>
          <div><Label htmlFor="mp-cap" hint={`${profile.active} now`}>Students at once</Label>
            <Select id="mp-cap" value={f.capacity} onChange={(e) => setF({ ...f, capacity: Number(e.target.value) })}>
              {[1, 2, 3, 5, 8, 10, 15, 20].filter((n) => n <= ws.max_capacity).map((n) => <option key={n} value={n}>{n}</option>)}</Select></div>
        </div>
        <div className="flex items-center gap-3 border-t border-line pt-4">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">Taking new students</div>
            <div className="text-xs text-muted">Turn it off to stop new requests. Your seekers, calls and sessions carry on.</div>
          </div>
          <Switch checked={f.accepting} onChange={(v) => setF({ ...f, accepting: v })} label="Taking new students" />
        </div>
        <div className="flex justify-end"><Button variant="primary" disabled={!ok} loading={save.isPending} onClick={() => save.mutate()}>Save card</Button></div>
      </div>
    </Card>
  );
}

/** Sign-in details: name, password, sign out, and deleting the account with everything in it. */
function Account() {
  const navigate = useNavigate();
  const { user, setAuth, logout } = useAuth();
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ password: "", confirm: "" });
  const changePw = useMutation({
    mutationFn: () => api.changePassword(pw),
    onSuccess: (r) => { setAuth(r.access_token, r.user); setPw({ current_password: "", new_password: "" }); toast.success("Password updated. Other devices are signed out."); },
    onError: failed,
  });
  const remove = useMutation({
    mutationFn: () => api.deleteAccount(form),
    onSuccess: () => { logout(); navigate("/", { replace: true }); toast.success("Your account and all its data were deleted."); },
    onError: failed,
  });
  return (
    <Card>
      <CardHeader title="Account" icon={<KeyRound className="h-4 w-4" />} subtitle={`${user?.full_name} · ${user?.email}`} />
      <div className="grid gap-5 p-5 md:grid-cols-2">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); changePw.mutate(); }}>
          <div className="text-sm font-medium">Change password</div>
          <Input type="password" aria-label="Current password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" />
          <Input type="password" aria-label="New password" placeholder="New password (8+ characters)" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" minLength={8} />
          <Button type="submit" disabled={!pw.current_password || pw.new_password.length < 8} loading={changePw.isPending}>Update password</Button>
        </form>
        <div className="space-y-3">
          <div className="text-sm font-medium">Leaving</div>
          <p className="text-xs text-muted">Deleting removes your profile, your conversations with seekers, your calls and your master sessions. Students with a call or seat still to come are told, and refunded what they paid. This can't be undone.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<LogOut className="h-3.5 w-3.5" />} onClick={logout}>Sign out</Button>
            <Button variant="danger" icon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setOpen(true)}>Delete account</Button>
          </div>
        </div>
      </div>
      <Dialog open={open} onClose={() => !remove.isPending && setOpen(false)} title="Delete your mentor account?"
        subtitle="Your seekers lose their conversations with you, and students in your upcoming sessions are told it's off.">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); remove.mutate(); }}>
          <div><Label htmlFor="mp-del-pw">Your password</Label><Input id="mp-del-pw" type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <div><Label htmlFor="mp-del-confirm">Type DELETE to confirm</Label><Input id="mp-del-confirm" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} placeholder="DELETE" /></div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Keep my account</Button>
            <Button type="submit" variant="danger" loading={remove.isPending} disabled={form.confirm !== "DELETE" || !form.password}>Delete everything</Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}

/** The mentor's profile: their public card and price once approved, and their account either way. */
export default function MentorProfilePage() {
  const { data: ws, isLoading } = useWorkspace();
  if (isLoading || !ws) return <Skeleton className="mx-auto h-72 max-w-4xl" />;
  const p = ws.profile;
  const approved = p?.status === "approved";
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader eyebrow="Profile" title="Your profile" subtitle="Your public card, your price and your account." />
      {approved && p ? (
        <>
          <PhotoCard profile={p} />
          <PublicProfile key={p.id} ws={ws} profile={p} />
          <PriceCard ws={ws} profile={p} />
        </>
      ) : (
        <Card className="p-5">
          <div className="text-sm font-medium">{p ? "Your card opens once you're approved" : "You haven't applied yet"}</div>
          <p className="mt-1 text-sm text-muted">
            {p ? "Until Focs approves your application, you can change your details by resending it from the overview." : "Apply with your qualifications, and your public card and price open here once Focs approves you."}
          </p>
          <Link to="/mentor" className="mt-4 inline-block"><Button variant="primary">{p ? "See my application" : "Apply now"}</Button></Link>
        </Card>
      )}
      {p && !approved && <PhotoCard profile={p} />}
      <Account />
    </div>
  );
}
