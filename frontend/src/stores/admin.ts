import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface AdminState {
  token: string | null;
  username: string | null;
  expiresAt: number | null;
  signIn: (token: string, username: string, expiresInSeconds: number) => void;
  signOut: () => void;
}

/**
 * The admin panel's session, kept apart from the student login. It lives in sessionStorage, so closing the
 * browser signs the admin out, and it expires on its own after a few hours either way.
 */
export const useAdmin = create<AdminState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      expiresAt: null,
      signIn: (token, username, expiresInSeconds) => set({ token, username, expiresAt: Date.now() + expiresInSeconds * 1000 }),
      signOut: () => set({ token: null, username: null, expiresAt: null }),
    }),
    { name: "focs-admin", storage: createJSONStorage(() => sessionStorage) },
  ),
);

export const adminSignedIn = () => {
  const { token, expiresAt } = useAdmin.getState();
  return !!token && !!expiresAt && expiresAt > Date.now();
};
