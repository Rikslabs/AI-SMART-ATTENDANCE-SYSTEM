import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function StudentAttendance() {
  const [rows, setRows] = useState([]);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/attendance", { params: { month } });
      setRows(r.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [month]);

  return (
    <div className="space-y-6" data-testid="my-attendance-page">
      <div>
        <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// HISTORY</div>
        <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">My Attendance</h1>
      </div>

      <div>
        <input data-testid="my-attendance-month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="px-3 py-2 border border-[var(--sa-border)] rounded-md text-sm" />
      </div>

      <div className="border border-[var(--sa-border)] bg-white rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--sa-surface)] border-b border-[var(--sa-border)]">
            <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sa-muted)]">
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={3} className="text-center py-10 text-[var(--sa-muted)]">Loading…</td></tr>}
            {!loading && rows.length === 0 && <tr><td colSpan={3} className="text-center py-10 text-[var(--sa-muted)]">No records for this month.</td></tr>}
            {rows.map(r => (
              <tr key={r.id} className="sa-row border-b border-[var(--sa-border)] last:border-0">
                <td className="px-5 py-3 font-mono-tech">{r.date}</td>
                <td className="px-5 py-3 font-mono-tech">{new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                <td className="px-5 py-3">
                  <span className="inline-block px-2 py-0.5 text-[10px] font-mono-tech uppercase tracking-widest bg-[var(--sa-success)]/10 text-[var(--sa-success)] border border-[var(--sa-success)]/30 rounded">{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
