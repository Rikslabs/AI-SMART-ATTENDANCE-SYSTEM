import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("sa_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const s = err?.response?.status;
    const detail = err?.response?.data?.detail || "";
    if (s === 401) {
      localStorage.removeItem("sa_token");
      localStorage.removeItem("sa_user");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    } else if (s === 403 && /password change required/i.test(detail)) {
      // Sync user state so ProtectedRoute renders the forced change screen.
      try {
        const u = JSON.parse(localStorage.getItem("sa_user") || "null");
        if (u && !u.force_password_change) {
          u.force_password_change = true;
          localStorage.setItem("sa_user", JSON.stringify(u));
          window.location.reload();
        }
      } catch {
        // ignore
      }
    }
    return Promise.reject(err);
  }
);
