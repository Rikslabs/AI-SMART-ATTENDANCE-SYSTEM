import React, { useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import { toast } from "sonner";
import { DownloadSimple, MagnifyingGlass, CalendarBlank } from "@phosphor-icons/react";

export default function AttendancePage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState("day"); // day | month
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (mode === "day") params.date = date;
      else params.month = month;
      if (search) params.search = search;
      const r = await api.get("/attendance", { params });
      setRows(r.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [mode, date, month]);

  const doSearch = (e) => { e.preventDefault(); load(); };

  const exportCsv = async () => {
    try {
      const token = localStorage.getItem("sa_token");
      const params = new URLSearchParams();
      if (mode === "day") params.set("date", date);
      else params.set("month", month);
      const url = `${API}/attendance/export?${params.toString()}`;
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `attendance_${mode === "day" ? date : month}.csv`;
      a.click();
      toast.success("Exported");
    } catch { toast.error("Export failed"); }
  };

  return (
    <div className="space-y-6" data-testid="attendance-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// RECORDS</div>
          <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Attendance</h1>
          <p className="text-sm text-[var(--sa-muted)] mt-1">Filter by day or month, search students, and export CSV reports.</p>
        </div>
        <button data-testid="export-csv-button" onClick={exportCsv} className="bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white text-sm font-medium px-4 py-2.5 rounded-md flex items-center gap-2">
          <DownloadSimple size={14} weight="bold" /> Export CSV
        </button>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex border border-[var(--sa-border)] rounded-md overflow-hidden">
          <button data-testid="filter-day" onClick={() => setMode("day")} className={`px-4 py-2 text-sm ${mode === "day" ? "bg-[var(--sa-primary)] text-white" : "bg-white hover:bg-[var(--sa-surface)]"}`}>Daily</button>
          <button data-testid="filter-month" onClick={() => setMode("month")} className={`px-4 py-2 text-sm ${mode === "month" ? "bg-[var(--sa-primary)] text-white" : "bg-white hover:bg-[var(--sa-surface)]"}`}>Monthly</button>
        </div>
        {mode === "day" ? (
          <input data-testid="filter-date-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="px-3 py-2 border border-[var(--sa-border)] rounded-md text-sm" />
        ) : (
          <input data-testid="filter-month-input" type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="px-3 py-2 border border-[var(--sa-border)] rounded-md text-sm" />
        )}
        <form onSubmit={doSearch} className="relative">
          <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--sa-muted)]" size={14} />
          <input data-testid="attendance-search" placeholder="Search name / roll…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-8 pr-3 py-2 border border-[var(--sa-border)] rounded-md text-sm w-64" />
        </form>
      </div>

      <div className="border border-[var(--sa-border)] bg-white rounded-md overflow-hidden">
        <table className="w-full text-sm" data-testid="attendance-table">
          <thead className="bg-[var(--sa-surface)] border-b border-[var(--sa-border)]">
            <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sa-muted)]">
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Roll No.</th>
              <th className="px-5 py-3">Student</th>
              <th className="px-5 py-3">Course</th>
              <th className="px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="text-center py-10 text-[var(--sa-muted)]">Loading…</td></tr>}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={6} className="text-center py-10 text-[var(--sa-muted)]">No attendance records for this period.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="sa-row border-b border-[var(--sa-border)] last:border-0">
                <td className="px-5 py-3 font-mono-tech">{r.date}</td>
                <td className="px-5 py-3 font-mono-tech">{new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td>
                <td className="px-5 py-3 font-mono-tech">{r.roll_number}</td>
                <td className="px-5 py-3">{r.student_name}</td>
                <td className="px-5 py-3">{r.course}</td>
                <td className="px-5 py-3">
                  <span className="inline-block px-2 py-0.5 text-[10px] font-mono-tech uppercase tracking-widest bg-[var(--sa-success)]/10 text-[var(--sa-success)] border border-[var(--sa-success)]/30 rounded">
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs font-mono-tech text-[var(--sa-muted)] flex items-center gap-2">
        <CalendarBlank size={12} /> {rows.length} records
      </div>
    </div>
  );
}
