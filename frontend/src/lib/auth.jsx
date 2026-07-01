import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("sa_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("sa_token");
    if (t && !user) {
      api.get("/auth/me").then(r => {
        setUser(r.data);
        localStorage.setItem("sa_user", JSON.stringify(r.data));
      }).catch(() => {});
    }
  // eslint-disable-next-line
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
    <AuthCtx.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
