import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Users, ClipboardText, ChartBar, IdentificationBadge, ArrowRight } from "@phosphor-icons/react";
import { Link } from "react-router-dom";
import OnboardingCard from "@/components/OnboardingCard";

function StatCard({ label, value, icon: Icon, hint, tid }) {
  return (
    <div data-testid={tid} className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-6 hover:border-[var(--sa-border-strong)] hover:shadow-sm transition-all rounded-md">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--sa-muted)]">{label}</div>
          <div className="font-mono-tech text-4xl font-semibold text-[var(--sa-text)] mt-3">{value}</div>
          {hint && <div className="text-xs text-[var(--sa-muted)] mt-2">{hint}</div>}
        </div>
        <div className="w-10 h-10 bg-white border border-[var(--sa-border)] flex items-center justify-center">
          <Icon size={20} weight="bold" color="#0033CC" />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/attendance/stats");
      setStats(r.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const maxWeek = Math.max(1, ...(stats?.week?.map(w => w.count) || [1]));

  return (
    <div className="space-y-8" data-testid="admin-dashboard">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// OVERVIEW</div>
          <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Dashboard</h1>
          <p className="text-[var(--sa-muted)] mt-1 text-sm">Live snapshot of attendance activity across your campus.</p>
        </div>
        <div className="flex gap-3">
          <Link to="/scan" data-testid="dashboard-scan-cta" className="bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white text-sm font-medium px-4 py-2.5 rounded-md flex items-center gap-2 transition-all">
            Start Face Scan <ArrowRight size={14} weight="bold" />
          </Link>
          <Link to="/students/new" data-testid="dashboard-add-student-cta" className="border border-[var(--sa-border)] hover:bg-[var(--sa-surface)] text-sm font-medium px-4 py-2.5 rounded-md transition-all">
            + Add Student
          </Link>
        </div>
      </div>

      <OnboardingCard />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard tid="stat-total-students" label="Total Students" value={stats?.total_students ?? "–"} icon={Users} hint="Registered in system" />
        <StatCard tid="stat-today-attendance" label="Today's Attendance" value={stats?.today_attendance ?? "–"} icon={ClipboardText} hint={new Date().toDateString()} />
        <StatCard tid="stat-percentage" label="Attendance %" value={`${stats?.attendance_percentage ?? 0}%`} icon={ChartBar} hint="Today vs total" />
        <StatCard tid="stat-face-enrolled" label="Face Enrolled" value={stats?.face_enrolled ?? "–"} icon={IdentificationBadge} hint="Ready for scanning" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Week chart */}
        <div className="lg:col-span-2 bg-white border border-[var(--sa-border)] p-6 rounded-md">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)]">Last 7 Days</div>
              <div className="font-heading text-lg font-semibold">Attendance Trend</div>
            </div>
          </div>
          <div className="flex items-end gap-3 h-48">
            {(stats?.week || []).map((w) => (
              <div key={w.date} className="flex-1 flex flex-col items-center gap-2">
                <div className="w-full flex-1 flex items-end">
                  <div
                    className="w-full bg-[var(--sa-primary)] transition-all hover:bg-[var(--sa-primary-hover)]"
                    style={{ height: `${(w.count / maxWeek) * 100}%`, minHeight: "3px" }}
                    title={`${w.count} on ${w.date}`}
                  />
                </div>
                <div className="font-mono-tech text-[10px] text-[var(--sa-muted)]">{w.date.slice(5)}</div>
                <div className="font-mono-tech text-xs font-semibold">{w.count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent */}
        <div className="bg-white border border-[var(--sa-border)] p-6 rounded-md">
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-1">Latest</div>
          <div className="font-heading text-lg font-semibold mb-4">Recent Check-ins</div>
          <div className="space-y-3">
            {(stats?.recent || []).length === 0 && (
              <div className="text-sm text-[var(--sa-muted)]">No attendance yet. Head to Face Scan to start.</div>
            )}
            {(stats?.recent || []).map((r) => (
              <div key={r.id} className="flex items-center justify-between text-sm border-b border-[var(--sa-border)] pb-3 last:border-0">
                <div className="min-w-0">
                  <div className="font-medium truncate">{r.student_name}</div>
                  <div className="font-mono-tech text-[11px] text-[var(--sa-muted)]">{r.roll_number} · {r.course}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-mono-tech text-xs">{new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                  <div className="font-mono-tech text-[10px] text-[var(--sa-muted)]">{r.date}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {loading && <div className="text-sm text-[var(--sa-muted)]">Loading…</div>}
    </div>
  );
}
