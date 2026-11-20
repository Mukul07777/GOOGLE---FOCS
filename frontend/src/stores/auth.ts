import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/lib/types";

interface AuthState {
  token: string | null;
  user: User | null;
  /** where the sign-in/sign-up page should go once signed in (the guest-only guard follows it) */
  redirect: string | null;
  setAuth: (token: string, user: User, redirect?: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      redirect: null,
      setAuth: (token, user, redirect) => set((s) => ({ token, user, redirect: redirect ?? s.redirect })),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null, redirect: null }),
    }),
    { name: "focs-auth", partialize: (s) => ({ token: s.token, user: s.user }) },
  ),
);
