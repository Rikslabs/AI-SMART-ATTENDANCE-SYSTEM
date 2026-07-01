import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("sa_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    const t = localStorage.getItem("sa_token");
    if (!t) return null;
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
      localStorage.setItem("sa_user", JSON.stringify(r.data));
      return r.data;
    } catch { return null; }
  };

  useEffect(() => {
    const t = localStorage.getItem("sa_token");
    if (t) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const r = await api.post("/auth/login", { email, password });
      localStorage.setItem("sa_token", r.data.access_token);
      localStorage.setItem("sa_user", JSON.stringify(r.data.user));
      setUser(r.data.user);
      return r.data.user;
    } finally { setLoading(false); }
  };

  const logout = () => {
    localStorage.removeItem("sa_token");
    localStorage.removeItem("sa_user");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthCtx.Provider value={{ user, login, logout, loading, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
