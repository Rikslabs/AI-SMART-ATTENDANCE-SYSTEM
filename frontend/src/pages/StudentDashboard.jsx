import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ChartBar, Calendar, CheckCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

export default function StudentDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => { api.get("/attendance/me/stats").then(r => setStats(r.data)); }, []);

  const pct = stats?.attendance_percentage || 0;

  return (
    <div className="space-y-8" data-testid="student-dashboard">
      <div>
        <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// STUDENT PORTAL</div>
        <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Welcome, {user?.name?.split(" ")[0]}</h1>
        <p className="text-sm text-[var(--sa-muted)] mt-1">Your attendance summary and history.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-6 rounded-md">
          <div className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--sa-muted)]">Present Days</div>
          <div className="font-mono-tech text-4xl font-semibold mt-3">{stats?.present_days ?? "–"}</div>
          <div className="text-xs text-[var(--sa-muted)] mt-2 flex items-center gap-1"><CheckCircle size={12} /> Days marked present</div>
        </div>
        <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-6 rounded-md">
          <div className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--sa-muted)]">Working Days</div>
          <div className="font-mono-tech text-4xl font-semibold mt-3">{stats?.working_days ?? "–"}</div>
          <div className="text-xs text-[var(--sa-muted)] mt-2 flex items-center gap-1"><Calendar size={12} /> Class days recorded</div>
        </div>
        <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-6 rounded-md">
          <div className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--sa-muted)]">Attendance %</div>
          <div className="font-mono-tech text-4xl font-semibold mt-3">{pct}%</div>
          <div className="mt-3 h-2 bg-[var(--sa-surface-alt)] rounded overflow-hidden">
            <div className="h-full bg-[var(--sa-primary)]" style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
        </div>
      </div>

      <div className="bg-white border border-[var(--sa-border)] p-6 rounded-md">
        <div className="flex items-center justify-between mb-4">
          <div className="font-heading font-semibold text-lg">Recent Check-ins</div>
          <Link to="/my/attendance" className="text-xs font-mono-tech uppercase tracking-widest text-[var(--sa-primary)] hover:underline">View all</Link>
        </div>
        <div className="divide-y divide-[var(--sa-border)]">
          {(stats?.recent || []).length === 0 && <div className="text-sm text-[var(--sa-muted)] py-4">No attendance records yet.</div>}
          {(stats?.recent || []).slice(0, 6).map((r) => (
            <div key={r.id} className="flex items-center justify-between py-3 text-sm">
              <div className="font-mono-tech">{r.date}</div>
              <div className="font-mono-tech text-[var(--sa-muted)]">{new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
              <span className="inline-block px-2 py-0.5 text-[10px] font-mono-tech uppercase tracking-widest bg-[var(--sa-success)]/10 text-[var(--sa-success)] border border-[var(--sa-success)]/30 rounded">
                {r.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
