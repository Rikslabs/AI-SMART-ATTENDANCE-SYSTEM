import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { loadFaceModels, detectFaceDescriptor, drawBox } from "@/lib/faceApi";
import { openCamera, stopStream } from "@/lib/camera";
import { Camera, ArrowLeft, CheckCircle, XCircle, WarningCircle, Pulse } from "@phosphor-icons/react";

const StatusPill = ({ tone = "muted", children }) => {
  const map = {
    success: "text-[var(--sa-success)] border-[var(--sa-success)]/30 bg-[var(--sa-success)]/10",
    danger: "text-[var(--sa-danger)] border-[var(--sa-danger)]/30 bg-[var(--sa-danger)]/10",
    warning: "text-[var(--sa-warning)] border-[var(--sa-warning)]/30 bg-[var(--sa-warning)]/10",
    muted: "text-[var(--sa-muted)] border-[var(--sa-border)] bg-white",
  }[tone];
  return <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-mono-tech uppercase tracking-widest border rounded ${map}`}>{children}</span>;
};

export default function StudentScan() {
  const { user } = useAuth();
  const nav = useNavigate();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const streamRef = useRef(null);
  const busy = useRef(false);

  const [modelsReady, setModelsReady] = useState(false);
  const [modelsError, setModelsError] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [detected, setDetected] = useState(false);
  const [status, setStatus] = useState("Loading AI models…");
  const [result, setResult] = useState(null); // { tone, title, subtitle, time }
  const [busyMark, setBusyMark] = useState(false);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    if (user?.id) {
      api.get(`/students/${user.id}`).then(r => setProfile(r.data)).catch(() => {});
    }
    loadFaceModels()
      .then(() => { setModelsReady(true); setStatus("Models ready. Start camera to mark attendance."); })
      .catch((e) => { setModelsError(e?.message || "Failed to load models."); setStatus("Model load failed."); });
    return () => stop();
    // eslint-disable-next-line
  }, [user?.id]);

  const stop = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    stopStream(streamRef.current);
    streamRef.current = null;
    setStreaming(false);
  };

  const start = async () => {
    setCameraError(null);
    setResult(null);
    try {
      const { stream } = await openCamera({ width: 640, height: 480 });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setStreaming(true);
      setStatus("Position your face inside the frame…");
      loop();
    } catch (e) {
      setCameraError({ code: e.code, message: e.message });
      toast.error(e.message || "Camera access failed");
    }
  };

  const loop = async () => {
    if (!videoRef.current || !modelsReady) { rafRef.current = requestAnimationFrame(loop); return; }
    const r = await detectFaceDescriptor(videoRef.current);
    drawBox(canvasRef.current, videoRef.current, r?.box, r ? "#0033CC" : "#EF4444");
    setDetected(!!r);
    if (!busyMark && !result) setStatus(r ? "Face detected. Tap 'Mark My Attendance'." : "No face detected — adjust lighting/angle.");
    rafRef.current = requestAnimationFrame(loop);
  };

  const mark = async () => {
    if (busy.current) return;
    busy.current = true;
    setBusyMark(true);
    setResult(null);
    try {
      const r = await detectFaceDescriptor(videoRef.current);
      if (!r) {
        setResult({ tone: "danger", title: "No face detected", subtitle: "Try again with a clear frontal face." });
        toast.error("No face detected. Try again.");
        return;
      }
      const res = await api.post("/face/mark-self", { descriptor: r.descriptor });
      const data = res.data;
      if (!data.matched && data.reason === "not_enrolled") {
        setResult({ tone: "warning", title: "Not enrolled", subtitle: data.message });
        toast.warning(data.message);
      } else if (!data.matched) {
        setResult({ tone: "danger", title: "Face didn't match", subtitle: data.message || "Please try again in better lighting." });
        toast.error(data.message || "Face didn't match");
      } else if (data.already_marked) {
        setResult({
          tone: "warning", title: "Already marked today",
          subtitle: `Recorded at ${new Date(data.attendance.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.`,
        });
        toast.info("Attendance already marked today");
        setTimeout(stop, 900);
      } else {
        setResult({
          tone: "success", title: "Attendance marked!",
          subtitle: `Recorded at ${new Date(data.attendance.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.`,
        });
        toast.success("Attendance marked successfully");
        setTimeout(() => { stop(); nav("/my"); }, 1500);
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || "Something went wrong. Please try again.";
      setResult({ tone: "danger", title: "Error", subtitle: msg });
      toast.error(msg);
    } finally {
      busy.current = false;
      setBusyMark(false);
    }
  };

  return (
    <div className="max-w-4xl" data-testid="student-scan-page">
      <Link to="/my" className="inline-flex items-center gap-1 text-sm text-[var(--sa-muted)] hover:text-[var(--sa-primary)] mb-4">
        <ArrowLeft size={14} /> Back to Dashboard
      </Link>
      <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// SELF ATTENDANCE</div>
      <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-1">Mark Your Attendance</h1>
      <p className="text-sm text-[var(--sa-muted)] mb-6">
        Use your webcam to verify your identity. We compare against your registered face only.
      </p>

      {profile && !profile.face_enrolled && (
        <div className="mb-6 p-4 border border-[var(--sa-warning)]/40 bg-[var(--sa-warning)]/10 rounded-md flex items-start gap-3" data-testid="not-enrolled-banner">
          <WarningCircle size={20} className="text-[var(--sa-warning)] shrink-0 mt-0.5" weight="fill" />
          <div className="text-sm">
            <div className="font-medium text-[var(--sa-text)]">Face not enrolled</div>
            <div className="text-[var(--sa-muted)]">Your face isn&apos;t registered yet. Please ask your administrator to enroll you before you can self-mark attendance.</div>
          </div>
        </div>
      )}

      {modelsError && (
        <div className="mb-6 p-4 border border-[var(--sa-danger)]/40 bg-[var(--sa-danger)]/10 rounded-md flex items-start gap-3" data-testid="models-error-banner">
          <XCircle size={20} className="text-[var(--sa-danger)] shrink-0 mt-0.5" weight="fill" />
          <div className="text-sm text-[var(--sa-text)]">Failed to load AI models: {modelsError}. Check your internet connection and reload the page.</div>
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-6">
        {/* Camera */}
        <div className="md:col-span-2 border border-black bg-black relative overflow-hidden tech-grid rounded-md">
          <video ref={videoRef} className="w-full block" muted playsInline />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
          {streaming && <div className={`scan-line ${result?.tone === "success" ? "success" : ""}`} />}
          {!streaming && (
            <div className="aspect-[4/3] flex flex-col items-center justify-center text-white/60 font-mono-tech text-sm gap-2">
              <Camera size={40} weight="thin" />
              <div>CAMERA OFFLINE</div>
            </div>
          )}
          {streaming && (
            <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/70 px-3 py-1.5 rounded-md">
              <Pulse size={14} weight="fill" color={detected ? "#10B981" : "#EF4444"} />
              <span className="font-mono-tech text-[10px] tracking-widest uppercase text-white">
                {detected ? "FACE DETECTED" : "NO FACE"}
              </span>
            </div>
          )}
          <div className="absolute bottom-0 left-0 right-0 px-4 py-2 bg-black/70 text-white font-mono-tech text-[11px] tracking-widest uppercase">
            {status}
          </div>
        </div>

        {/* Controls */}
        <div className="space-y-4">
          {cameraError && (
            <div className="p-4 border border-[var(--sa-danger)]/40 bg-[var(--sa-danger)]/10 rounded-md" data-testid="camera-error-banner">
              <div className="flex items-center gap-2 text-[var(--sa-danger)] font-mono-tech text-[11px] uppercase tracking-widest mb-1">
                <XCircle size={14} weight="fill" /> {cameraError.code}
              </div>
              <div className="text-sm text-[var(--sa-text)]">{cameraError.message}</div>
              <button onClick={start} data-testid="retry-camera" className="mt-3 w-full border border-[var(--sa-border)] hover:bg-white py-2 rounded-md text-sm">Retry</button>
            </div>
          )}

          {!streaming ? (
            <button
              data-testid="student-start-camera"
              onClick={start}
              disabled={!modelsReady || (profile && !profile.face_enrolled)}
              className="w-full bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium py-2.5 rounded-md disabled:opacity-60 flex items-center justify-center gap-2 transition-all"
            >
              <Camera size={16} weight="bold" /> Start Camera
            </button>
          ) : (
            <>
              <button
                data-testid="student-mark-attendance"
                onClick={mark}
                disabled={!detected || busyMark}
                className="w-full bg-[var(--sa-success)] hover:opacity-90 text-white font-medium py-2.5 rounded-md disabled:opacity-60 flex items-center justify-center gap-2 transition-all"
              >
                <CheckCircle size={16} weight="bold" /> {busyMark ? "Verifying…" : "Mark My Attendance"}
              </button>
              <button data-testid="student-stop-camera" onClick={stop} className="w-full border border-[var(--sa-border)] hover:bg-[var(--sa-surface)] py-2.5 rounded-md text-sm">Stop Camera</button>
            </>
          )}

          {result && (
            <div
              data-testid="scan-result"
              className={`p-4 rounded-md border ${
                result.tone === "success" ? "border-[var(--sa-success)]" :
                result.tone === "warning" ? "border-[var(--sa-warning)]" :
                "border-[var(--sa-danger)]"
              } bg-white`}
            >
              <div className="mb-2">
                <StatusPill tone={result.tone}>
                  {result.tone === "success" ? <><CheckCircle size={12} weight="fill" /> Success</> :
                    result.tone === "warning" ? <><WarningCircle size={12} weight="fill" /> Notice</> :
                    <><XCircle size={12} weight="fill" /> Failed</>}
                </StatusPill>
              </div>
              <div className="font-heading font-semibold">{result.title}</div>
              <div className="text-sm text-[var(--sa-muted)] mt-1">{result.subtitle}</div>
            </div>
          )}

          <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-4 rounded-md text-xs text-[var(--sa-muted)] space-y-1">
            <div className="font-mono-tech uppercase tracking-widest text-[10px] mb-2 text-[var(--sa-text)]">Tips</div>
            <div>· Face the camera directly</div>
            <div>· Ensure good lighting on your face</div>
            <div>· Remove sunglasses / masks</div>
            <div>· Keep only your face in the frame</div>
          </div>
        </div>
      </div>
    </div>
  );
}
