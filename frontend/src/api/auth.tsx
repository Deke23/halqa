import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, clearSession, getToken, onUnauthorized, readStoredUser, storeSession } from "./client";
import type { AuthResponse, Persona, User } from "./types";

interface AuthValue {
  user: User | null;
  persona: Persona | null;
  isSignedIn: boolean;
  /** Throws a normalised ApiError. status 0 means the backend is unreachable. */
  loginAsGuest: (persona: Persona) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(() => (getToken() ? readStoredUser<User>() : null));

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    qc.clear();
  }, [qc]);

  // A 401 from any request signs the user out.
  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null);
        qc.clear();
      }),
    [qc],
  );

  const loginAsGuest = useCallback(
    async (persona: Persona) => {
      const res = await api<AuthResponse>("/auth/guest", { method: "POST", body: { persona }, anonymous: true });
      const u: User = { ...res.user, persona: res.user.persona ?? persona };
      storeSession(res.token, u);
      qc.clear();
      setUser(u);
      return u;
    },
    [qc],
  );

  const value = useMemo<AuthValue>(
    () => ({
      user,
      persona: (user?.persona as Persona | undefined) ?? null,
      isSignedIn: !!user,
      loginAsGuest,
      logout,
    }),
    [user, loginAsGuest, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
