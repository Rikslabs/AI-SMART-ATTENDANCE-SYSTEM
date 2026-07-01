import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, PencilSimple, Trash, Camera, MagnifyingGlass, CheckCircle, XCircle } from "@phosphor-icons/react";

export default function StudentsPage() {
  const [students, setStudents] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/students");
      setStudents(r.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const del = async (s) => {
    if (!confirm(`Delete student "${s.name}"? This removes their attendance too.`)) return;
    try {
      await api.delete(`/students/${s.id}`);
      toast.success("Student deleted");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  const filtered = students.filter(s =>
    !q || [s.name, s.roll_number, s.email, s.course, s.phone].join(" ").toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="students-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// DIRECTORY</div>
          <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Students</h1>
          <p className="text-[var(--sa-muted)] mt-1 text-sm">Manage students and enroll their face for automatic attendance.</p>
        </div>
        <Link to="/students/new" data-testid="add-student-button" className="bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white text-sm font-medium px-4 py-2.5 rounded-md flex items-center gap-2 transition-all">
          <Plus size={14} weight="bold" /> Add Student
        </Link>
      </div>

      <div className="relative max-w-md">
        <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--sa-muted)]" size={16} />
        <input
          data-testid="students-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by name, roll, email…"
          className="pl-9 pr-4 py-2.5 w-full border border-[var(--sa-border)] rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent"
        />
      </div>

      <div className="border border-[var(--sa-border)] bg-white rounded-md overflow-hidden">
        <table className="w-full text-sm" data-testid="students-table">
          <thead className="bg-[var(--sa-surface)] border-b border-[var(--sa-border)]">
            <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sa-muted)]">
              <th className="px-5 py-3">Student</th>
              <th className="px-5 py-3">Roll No.</th>
              <th className="px-5 py-3">Course</th>
              <th className="px-5 py-3">Contact</th>
              <th className="px-5 py-3">Face</th>
              <th className="px-5 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} className="text-center py-10 text-[var(--sa-muted)]">Loading…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={6} className="text-center py-10 text-[var(--sa-muted)]">No students found.</td></tr>
            )}
            {filtered.map((s) => (
              <tr key={s.id} className="sa-row border-b border-[var(--sa-border)] last:border-0" data-testid={`student-row-${s.roll_number}`}>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-[var(--sa-primary)] text-white flex items-center justify-center font-heading font-bold">
                      {s.name?.[0]}
                    </div>
                    <div>
                      <div className="font-medium">{s.name}</div>
                      <div className="font-mono-tech text-[11px] text-[var(--sa-muted)]">{s.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 font-mono-tech">{s.roll_number}</td>
                <td className="px-5 py-4">{s.course}</td>
                <td className="px-5 py-4 font-mono-tech text-[13px]">{s.phone}</td>
                <td className="px-5 py-4">
                  {s.face_enrolled ? (
                    <span className="inline-flex items-center gap-1 text-xs text-[var(--sa-success)] font-mono-tech uppercase">
                      <CheckCircle size={14} weight="fill" /> Enrolled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-[var(--sa-danger)] font-mono-tech uppercase">
                      <XCircle size={14} weight="fill" /> Not enrolled
                    </span>
                  )}
                </td>
                <td className="px-5 py-4 text-right">
                  <div className="inline-flex gap-1">
                    <button
                      data-testid={`enroll-face-${s.roll_number}`}
                      onClick={() => nav(`/students/${s.id}/enroll`)}
                      title="Enroll face"
                      className="p-2 hover:bg-[var(--sa-surface)] rounded-md text-[var(--sa-primary)]"
                    ><Camera size={16} weight="bold" /></button>
                    <button
                      data-testid={`edit-student-${s.roll_number}`}
                      onClick={() => nav(`/students/${s.id}/edit`)}
                      title="Edit"
                      className="p-2 hover:bg-[var(--sa-surface)] rounded-md"
                    ><PencilSimple size={16} weight="bold" /></button>
                    <button
                      data-testid={`delete-student-${s.roll_number}`}
                      onClick={() => del(s)}
                      title="Delete"
                      className="p-2 hover:bg-[var(--sa-surface)] rounded-md text-[var(--sa-danger)]"
                    ><Trash size={16} weight="bold" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
