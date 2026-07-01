import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { GraduationCap, Lock, ArrowRight, WarningCircle, CheckCircle } from "@phosphor-icons/react";

/**
 * ChangePassword — used in TWO modes:
 *  - forced=true  → shown as a fullscreen block after login when user.force_password_change is true.
 *  - forced=false → normal settings page for any authenticated user.
 */
export default function ChangePassword({ forced = false }) {
  const { user, refresh, logout } = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  const validateNext = (pw) => {
    if (pw.length < 8) return "At least 8 characters";
    if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Must include at least one letter and one digit";
    if (["admin123", "student123", "password", "password1", "12345678"].includes(pw.toLowerCase())) return "Too common — pick a stronger one";
    if (pw === current) return "New password must be different from current";
    return null;
  };
  const nextError = next ? validateNext(next) : null;
  const matchError = confirm && next !== confirm ? "Passwords do not match" : null;
  const canSubmit = !!current && !!next && !nextError && !matchError && next === confirm;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      toast.success("Password changed successfully");
      await refresh();
      nav(user?.role === "admin" ? "/dashboard" : "/my", { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to change password");
    } finally { setSaving(false); }
  };

  const inner = (
    <form onSubmit={submit} className="space-y-4" data-testid="change-password-form">
      <div>
        <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">Current Password</label>
        <input
          data-testid="current-password-input"
          type="password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          className="mt-1.5 w-full px-4 py-2.5 border border-[var(--sa-border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent"
        />
      </div>
      <div>
        <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">New Password</label>
        <input
          data-testid="new-password-input"
          type="password"
          required
          value={next}
          onChange={(e) => setNext(e.target.value)}
          className={`mt-1.5 w-full px-4 py-2.5 border rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent ${nextError ? "border-[var(--sa-danger)]" : "border-[var(--sa-border)]"}`}
        />
        {nextError && <div className="mt-1 text-xs text-[var(--sa-danger)] font-mono-tech" data-testid="new-password-error">{nextError}</div>}
        {!nextError && next && (
          <div className="mt-1 text-xs text-[var(--sa-success)] font-mono-tech flex items-center gap-1"><CheckCircle size={12} weight="fill" /> Looks good</div>
        )}
      </div>
      <div>
        <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">Confirm New Password</label>
        <input
          data-testid="confirm-password-input"
          type="password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className={`mt-1.5 w-full px-4 py-2.5 border rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent ${matchError ? "border-[var(--sa-danger)]" : "border-[var(--sa-border)]"}`}
        />
        {matchError && <div className="mt-1 text-xs text-[var(--sa-danger)] font-mono-tech" data-testid="confirm-password-error">{matchError}</div>}
      </div>

      <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-3 rounded-md text-xs text-[var(--sa-muted)]">
        <div className="font-mono-tech uppercase tracking-widest text-[10px] mb-1 text-[var(--sa-text)]">Requirements</div>
        <ul className="space-y-0.5 list-disc list-inside">
          <li>At least 8 characters</li>
          <li>Contains a letter and a digit</li>
          <li>Not a common password</li>
          <li>Different from current password</li>
        </ul>
      </div>

      <button
        type="submit"
        data-testid="change-password-submit"
        disabled={!canSubmit || saving}
        className="w-full flex items-center justify-center gap-2 bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium py-2.5 rounded-md transition-all disabled:opacity-60"
      >
        {saving ? "Saving…" : (<>Update Password <ArrowRight size={16} weight="bold" /></>)}
      </button>

      {forced && (
        <button type="button" onClick={logout} data-testid="forced-logout" className="w-full text-xs text-[var(--sa-muted)] hover:text-[var(--sa-primary)] font-mono-tech uppercase tracking-widest">
          Log out instead
        </button>
      )}
    </form>
  );

  if (forced) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-6" data-testid="forced-change-password">
        <div className="w-full max-w-md">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-11 h-11 bg-[var(--sa-primary)] flex items-center justify-center">
              <GraduationCap size={26} color="#fff" weight="bold" />
            </div>
            <div>
              <div className="font-heading font-extrabold text-lg leading-tight">SMART ATTENDANCE</div>
              <div className="font-mono-tech text-[10px] tracking-[0.2em] text-[var(--sa-muted)] uppercase">Security · First Login</div>
            </div>
          </div>

          <div className="mb-6 p-4 border border-[var(--sa-warning)]/40 bg-[var(--sa-warning)]/10 rounded-md flex items-start gap-3">
            <WarningCircle size={20} className="text-[var(--sa-warning)] shrink-0 mt-0.5" weight="fill" />
            <div className="text-sm">
              <div className="font-medium text-[var(--sa-text)]">Password change required</div>
              <div className="text-[var(--sa-muted)]">You&apos;re signed in with a default password. Please set a new secure password to continue.</div>
            </div>
          </div>

          <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-2 flex items-center gap-2">
            <Lock size={22} weight="bold" /> Change your password
          </h1>
          <p className="text-sm text-[var(--sa-muted)] mb-6">Signed in as <span className="font-mono-tech text-[var(--sa-text)]">{user?.email}</span></p>
          {inner}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md" data-testid="settings-change-password">
      <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// SETTINGS</div>
      <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-1 flex items-center gap-2">
        <Lock size={22} weight="bold" /> Change Password
      </h1>
      <p className="text-sm text-[var(--sa-muted)] mb-6">Update your account password. You&apos;ll stay signed in on this device.</p>
      <div className="bg-white border border-[var(--sa-border)] p-6 rounded-md">{inner}</div>
    </div>
  );
}
