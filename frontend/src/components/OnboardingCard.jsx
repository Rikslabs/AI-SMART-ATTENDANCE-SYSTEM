import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { CheckCircle, Circle, ArrowRight, X, Rocket } from "@phosphor-icons/react";

const STEP_LINKS = {
  add_student: { to: "/students/new", cta: "Add a student" },
  enroll_face: { to: "/students", cta: "Enroll a face" },
  visit_scan: { to: "/scan", cta: "Open scanner" },
  first_attendance: { to: "/scan", cta: "Scan & mark" },
  visit_report: { to: "/attendance", cta: "View report" },
};

export default function OnboardingCard() {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/onboarding/status");
      setState(r.data);
    } catch { setState(null); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const dismiss = async () => {
    try {
      await api.post("/onboarding/dismiss");
      setState((s) => (s ? { ...s, dismissed: true } : s));
    } catch { /* ignore */ }
  };

  if (loading || !state || state.dismissed) return null;

  const { steps, completed, total } = state;
  const pct = Math.round((completed / total) * 100);
  const nextStep = steps.find((s) => !s.done);

  return (
    <div
      data-testid="onboarding-card"
      className="relative border border-[var(--sa-border-strong)] bg-[var(--sa-surface)] rounded-md p-6 overflow-hidden"
    >
      <button
        onClick={dismiss}
        data-testid="onboarding-dismiss"
        className="absolute top-3 right-3 p-1.5 rounded-md hover:bg-white text-[var(--sa-muted)] hover:text-[var(--sa-text)] transition-all"
        aria-label="Dismiss onboarding"
        title="Dismiss"
      >
        <X size={16} weight="bold" />
      </button>

      <div className="flex items-start gap-4 flex-wrap">
        <div className="w-11 h-11 bg-[var(--sa-primary)] flex items-center justify-center shrink-0 rounded-md">
          <Rocket size={22} color="#fff" weight="bold" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)]">
            // GETTING STARTED
          </div>
          <h2 className="font-heading text-lg sm:text-xl font-bold mt-0.5">
            {completed === total ? "All set — you're ready to go!" : "Let's set up your first attendance flow"}
          </h2>
          <p className="text-sm text-[var(--sa-muted)] mt-1">
            Complete these steps to see the whole system end-to-end.
          </p>

          {/* Progress */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-2 bg-white border border-[var(--sa-border)] rounded overflow-hidden">
              <div
                data-testid="onboarding-progress-bar"
                className="h-full bg-[var(--sa-primary)] transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="font-mono-tech text-xs" data-testid="onboarding-progress-text">
              {completed}/{total} · {pct}%
            </div>
          </div>
        </div>

        {nextStep && STEP_LINKS[nextStep.key] && (
          <Link
            to={STEP_LINKS[nextStep.key].to}
            data-testid="onboarding-next-cta"
            className="bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white text-sm font-medium px-4 py-2.5 rounded-md flex items-center gap-2 shrink-0 transition-all"
          >
            {STEP_LINKS[nextStep.key].cta} <ArrowRight size={14} weight="bold" />
          </Link>
        )}
      </div>

      {/* Step list */}
      <ol className="mt-6 grid sm:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="onboarding-steps">
        {steps.map((s, i) => {
          const link = STEP_LINKS[s.key];
          const Content = (
            <div
              data-testid={`onboarding-step-${s.key}`}
              className={`h-full p-3 border rounded-md transition-all ${
                s.done
                  ? "border-[var(--sa-success)]/40 bg-white"
                  : "border-[var(--sa-border)] bg-white hover:border-[var(--sa-border-strong)]"
              }`}
            >
              <div className="flex items-center gap-2">
                {s.done ? (
                  <CheckCircle size={18} weight="fill" color="#10B981" />
                ) : (
                  <Circle size={18} weight="regular" className="text-[var(--sa-muted)]" />
                )}
                <div className="font-mono-tech text-[10px] tracking-widest uppercase text-[var(--sa-muted)]">
                  Step {i + 1}
                </div>
              </div>
              <div className={`mt-1.5 text-sm font-medium leading-tight ${s.done ? "text-[var(--sa-text)]" : ""}`}>
                {s.label}
              </div>
            </div>
          );
          return (
            <li key={s.key}>
              {link ? <Link to={link.to} className="block h-full">{Content}</Link> : Content}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
