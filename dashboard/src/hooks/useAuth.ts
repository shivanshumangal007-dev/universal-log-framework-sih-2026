import { useState, useEffect, useCallback } from "react";

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("token");
    setToken(t);
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string, apiLogin: (u: string, p: string) => Promise<{ access_token: string }>) => {
    const res = await apiLogin(username, password);
    localStorage.setItem("token", res.access_token);
    setToken(res.access_token);
    return res;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
  }, []);

  return { token, ready, login, logout, isAuthenticated: !!token };
}
