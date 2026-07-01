import React, { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft } from "@phosphor-icons/react";

export default function StudentForm() {
  const { id } = useParams();
  const editing = !!id;
  const nav = useNavigate();
  const [f, setF] = useState({
    name: "", roll_number: "", email: "", course: "BCA", phone: "", password: "student123",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (editing) {
      api.get(`/students/${id}`).then(r => setF({ ...r.data, password: "" })).catch(() => nav("/students"));
    }
  }, [id, editing, nav]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing) {
        const payload = { ...f };
        delete payload.password;
        delete payload.face_enrolled;
        delete payload.face_image;
        delete payload.id;
        delete payload.created_at;
        await api.put(`/students/${id}`, payload);
        toast.success("Student updated");
      } else {
        await api.post(`/students`, f);
        toast.success("Student created");
      }
      nav("/students");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const set = (k, v) => setF(s => ({ ...s, [k]: v }));

  const field = (label, k, type = "text", required = true) => (
    <div>
      <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">{label}</label>
      <input
        data-testid={`form-${k}`}
        type={type}
        required={required}
        value={f[k] ?? ""}
        onChange={(e) => set(k, e.target.value)}
        className="mt-1.5 w-full px-4 py-2.5 border border-[var(--sa-border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)] focus:border-transparent"
      />
    </div>
  );

  return (
    <div className="max-w-2xl" data-testid="student-form-page">
      <Link to="/students" className="inline-flex items-center gap-1 text-sm text-[var(--sa-muted)] hover:text-[var(--sa-primary)] mb-4">
        <ArrowLeft size={14} /> Back to Students
      </Link>
      <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// {editing ? "EDIT" : "REGISTER"}</div>
      <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-6">{editing ? "Edit Student" : "Add New Student"}</h1>

      <form onSubmit={submit} className="space-y-5 bg-white border border-[var(--sa-border)] p-6 rounded-md">
        <div className="grid md:grid-cols-2 gap-5">
          {field("Full Name", "name")}
          {field("Roll Number", "roll_number")}
          {field("Email", "email", "email")}
          <div>
            <label className="text-xs uppercase tracking-[0.1em] font-bold text-[var(--sa-muted)]">Course</label>
            <select
              data-testid="form-course"
              value={f.course}
              onChange={(e) => set("course", e.target.value)}
              className="mt-1.5 w-full px-4 py-2.5 border border-[var(--sa-border)] rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-[var(--sa-primary)]"
            >
              {["BCA","MCA","B.Tech","M.Tech","B.Sc","M.Sc","BBA","MBA"].map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          {field("Phone", "phone")}
          {!editing && field("Initial Password", "password")}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            data-testid="save-student-button"
            type="submit"
            disabled={saving}
            className="bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium px-5 py-2.5 rounded-md disabled:opacity-60"
          >{saving ? "Saving…" : (editing ? "Save Changes" : "Create Student")}</button>
          <button type="button" onClick={() => nav("/students")} className="border border-[var(--sa-border)] hover:bg-[var(--sa-surface)] px-5 py-2.5 rounded-md text-sm">Cancel</button>
        </div>
      </form>
    </div>
  );
}
