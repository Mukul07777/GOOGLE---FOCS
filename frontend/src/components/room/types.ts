export interface Member { id: number; name: string; status: string; host?: boolean }

export interface Reply { id: string; user: string; user_id: number; text: string; at: number; accepted: boolean }

export interface ChatMsg {
  type: "chat" | "system" | "ai";
  id?: string;
  user?: string;
  user_id?: number;
  text?: string;
  kind?: "doubt" | "message";
  question?: string;
  answer?: string;
  at: number;
  /* doubts */
  votes?: number[];
  replies?: Reply[];
  resolved?: boolean;
  video_at?: number | null;
  ai_answer_id?: string;
  /* AI answers */
  doubt_id?: string | null;
}

export interface Score { user_id: number; name: string; points: number; correct: number; answered: number; helped?: number }

export interface NoteTaker { id: number; name: string }

export function clockOf(seconds: number) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
