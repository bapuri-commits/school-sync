import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Permission, UserInfo } from "../types";

interface AuthState {
  user: UserInfo | null;
  loading: boolean;
  error: string | null;
  hasPermission: (perm: Permission) => boolean;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  error: null,
  hasPermission: () => false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.me()
      .then(setUser)
      .catch((e) => setError(e.message ?? "인증 실패"))
      .finally(() => setLoading(false));
  }, []);

  const hasPermission = (perm: Permission) => {
    if (!user) return false;
    return user.permissions.includes(perm);
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
