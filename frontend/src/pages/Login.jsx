import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { GraduationCap, ArrowRight } from "@phosphor-icons/react";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("admin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const switchTab = (t) => {
    setTab(t);
    setEmail("");
    setPassword("");
  };

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome, ${u.name}`);
      nav(u.role === "admin" ? "/dashboard" : "/my");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-white">
      {/* Left branding */}
      <div className="hidden lg:flex flex-col justify-between p-12 relative overflow-hidden bg-[var(--sa-surface)] border-r border-[var(--sa-border)]">
        <div
          className="absolute inset-0 opacity-10 bg-cover bg-center"
          style={{ backgroundImage: `url(https://images.unsplash.com/photo-1641160616553-a9d21a846e49?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzV8MHwxfHNlYXJjaHwzfHx1bml2ZXJzaXR5JTIwY2FtcHVzJTIwYnVpbGRpbmd8ZW58MHx8fHwxNzgyOTE5MzA1fDA)` }}
        />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 bg-[var(--sa-primary)] flex items-center justify-center">
              <GraduationCap size={26} color="#fff" weight="bold" />
            </div>
            <div>
              <div className="font-heading font-extrabold text-lg leading-tight">SMART ATTENDANCE</div>
              <div className="font-mono-tech text-[10px] tracking-[0.2em] text-[var(--sa-muted)] uppercase">Face Recognition · AI</div>
            </div>
          </div>
        </div>
        <div className="relative z-10 max-w-md">
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-3">SYSTEM // v1.0</div>
          <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-extrabold leading-[0.95] mb-6">
            Attendance,<br />reimagined by AI.
          </h1>
          <p className="text-[var(--sa-muted)] leading-relaxed">
            Automatic face-based attendance marking for modern classrooms. Zero contact. Zero paperwork.
          </p>
        </div>
        <div className="relative z-10 font-mono-tech text-[10px] uppercase tracking-[0.2em] text-[var(--sa-muted)]">
          © College Attendance System
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// ACCESS TERMINAL</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Sign in to continue</h2>
            <p className="text-[var(--sa-muted)] mt-2 text-sm">Choose your role and enter credentials.</p>
          </div>

          <div className="flex border border-[var(--sa-border)] mb-6 rounded-md overflow-hidden">
            <button
              type="button"
              data-testid="login-tab-admin"
              onClick={() => switchTab("admin")}
              className={`flex-1 py-2.5 text-sm font-medium transition-all ${tab === "admin" ? "bg-[var(--sa-primary)] text-white" : "bg-white text-[var(--sa-text)] hover:bg-[var(--sa-surface)]"}`}
            >Admin</button>
            <button
              type="button"
              data-testid="login-tab-student"
              onClick={() => switchTab("student")}
              className={`flex-1 py-2.5 text-sm font-medium transition-all ${tab === "student" ? "bg-[var(--sa-primary)] text-white" : "bg-white text-[var(--sa-text)] hover:bg-[var(--sa-surface)]"}`}
            >Student</button>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">Email</label>
              <input
                data-testid="login-email-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full px-4 py-2.5 border border-[var(--sa-border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">Password</label>
              <input
                data-testid="login-password-input"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full px-4 py-2.5 border border-[var(--sa-border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent"
              />
            </div>
            <button
              type="submit"
              data-testid="login-submit-button"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium py-2.5 rounded-md transition-all disabled:opacity-60"
            >
              {loading ? "Signing in..." : (<>Sign in <ArrowRight size={16} weight="bold" /></>)}
            </button>
          </form>

          <div className="mt-6 p-4 border border-dashed border-[var(--sa-border)] rounded-md">
            <div className="text-xs font-mono-tech uppercase tracking-widest text-[var(--sa-muted)] mb-2">Access</div>
            <div className="text-xs text-[var(--sa-muted)]">
              Contact your administrator if you don&apos;t have login credentials.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
