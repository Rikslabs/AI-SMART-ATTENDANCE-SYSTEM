import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { loadFaceModels, detectFaceDescriptor, drawBox } from "@/lib/faceApi";
import { Camera, CheckCircle, XCircle, Pulse } from "@phosphor-icons/react";

export default function ScanPage() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const busy = useRef(false);
  const lastMatchAt = useRef(0);
  const [modelsReady, setModelsReady] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("Loading AI models…");
  const [detected, setDetected] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    loadFaceModels().then(() => { setModelsReady(true); setStatus("Models ready. Start scanning."); })
      .catch(() => setStatus("Failed to load models."));
    return () => stop();
    // eslint-disable-next-line
  }, []);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setStreaming(true);
      setStatus("Scanning for faces…");
      loop();
    } catch { toast.error("Camera access denied."); }
  };

  const stop = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const v = videoRef.current;
    if (v && v.srcObject) v.srcObject.getTracks().forEach(t => t.stop());
    setStreaming(false);
  };

  const loop = async () => {
    if (!videoRef.current || !modelsReady) { rafRef.current = requestAnimationFrame(loop); return; }
    const r = await detectFaceDescriptor(videoRef.current);
    drawBox(canvasRef.current, videoRef.current, r?.box, r ? "#0033CC" : "#EF4444");
    setDetected(!!r);

    // Recognize at most every 2 seconds
    if (r && !busy.current && Date.now() - lastMatchAt.current > 2000) {
      busy.current = true;
      try {
        const res = await api.post("/face/recognize", { descriptor: r.descriptor });
        if (res.data.matched) {
          lastMatchAt.current = Date.now();
          setLastResult(res.data);
          const entry = {
            ...res.data.student, ...res.data.attendance,
            already: res.data.already_marked, ts: Date.now(),
          };
          setHistory(h => [entry, ...h.filter(x => x.id !== entry.id).slice(0, 9)]);
          if (res.data.already_marked) {
            toast.info(`${res.data.student.name} — already marked today`);
          } else {
            toast.success(`${res.data.student.name} — attendance marked!`);
          }
          setStatus(`Recognized: ${res.data.student.name}`);
        } else {
          setStatus("Unknown face. Not registered.");
        }
      } catch { /* ignore */ }
      finally { busy.current = false; }
    }
    rafRef.current = requestAnimationFrame(loop);
  };

  return (
    <div className="space-y-6" data-testid="scan-page">
      <div>
        <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// LIVE RECOGNITION</div>
        <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Face Scan</h1>
        <p className="text-sm text-[var(--sa-muted)] mt-1">Point the camera at a student. Attendance is marked automatically.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 border border-black bg-black relative overflow-hidden tech-grid rounded-md">
          <video ref={videoRef} className="w-full block" muted playsInline />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
          {streaming && <div className={`scan-line ${lastResult?.matched && !lastResult?.already_marked ? "success" : ""}`} />}
          {!streaming && (
            <div className="aspect-video flex items-center justify-center text-white/60 font-mono-tech text-sm">
              CAMERA OFFLINE
            </div>
          )}
          <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/70 px-3 py-1.5 rounded-md">
            <Pulse size={14} weight="fill" color={detected ? "#10B981" : "#EF4444"} />
            <span className="font-mono-tech text-[10px] tracking-widest uppercase text-white">
              {detected ? "FACE DETECTED" : "NO FACE"}
            </span>
          </div>
          <div className="absolute bottom-0 left-0 right-0 px-4 py-2 bg-black/70 text-white font-mono-tech text-[11px] tracking-widest uppercase">
            {status}
          </div>
        </div>

        <div className="space-y-4">
          {!streaming ? (
            <button data-testid="start-scan-button" onClick={start} disabled={!modelsReady} className="w-full bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium py-2.5 rounded-md disabled:opacity-60 flex items-center justify-center gap-2">
              <Camera size={16} weight="bold" /> Start Scanning
            </button>
          ) : (
            <button data-testid="stop-scan-button" onClick={stop} className="w-full border border-[var(--sa-border)] hover:bg-[var(--sa-surface)] py-2.5 rounded-md text-sm">Stop Scanning</button>
          )}

          {/* Last Result Card */}
          {lastResult?.matched && (
            <div data-testid="scan-last-result" className={`border ${lastResult.already_marked ? "border-[var(--sa-warning)]" : "border-[var(--sa-success)]"} bg-white p-4 rounded-md`}>
              <div className="flex items-center gap-3">
                {lastResult.student.face_image ? (
                  <img src={lastResult.student.face_image} alt="face" className="w-14 h-14 rounded-md object-cover border border-[var(--sa-border)]" />
                ) : (
                  <div className="w-14 h-14 bg-[var(--sa-primary)] text-white rounded-md flex items-center justify-center font-heading font-bold text-xl">
                    {lastResult.student.name[0]}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="font-heading font-semibold truncate">{lastResult.student.name}</div>
                  <div className="font-mono-tech text-[11px] text-[var(--sa-muted)]">{lastResult.student.roll_number} · {lastResult.student.course}</div>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs">
                <div className={`flex items-center gap-1 font-mono-tech uppercase tracking-widest ${lastResult.already_marked ? "text-[var(--sa-warning)]" : "text-[var(--sa-success)]"}`}>
                  {lastResult.already_marked ? <><XCircle size={14} weight="fill" /> Already Marked</> : <><CheckCircle size={14} weight="fill" /> Marked</>}
                </div>
                <div className="font-mono-tech text-[var(--sa-muted)]">{new Date(lastResult.attendance.time).toLocaleTimeString()}</div>
              </div>
              <div className="mt-2 font-mono-tech text-[10px] text-[var(--sa-muted)]">
                Confidence distance: {lastResult.distance?.toFixed(3)}
              </div>
            </div>
          )}

          {/* History */}
          <div className="bg-white border border-[var(--sa-border)] p-4 rounded-md">
            <div className="font-mono-tech text-[10px] uppercase tracking-widest text-[var(--sa-muted)] mb-3">Session Log</div>
            <div className="space-y-2 max-h-72 overflow-auto">
              {history.length === 0 && <div className="text-xs text-[var(--sa-muted)]">No recognitions yet.</div>}
              {history.map((h) => (
                <div key={h.id + h.ts} className="flex items-center justify-between text-xs border-b border-[var(--sa-border)] pb-2 last:border-0">
                  <div>
                    <div className="font-medium">{h.name}</div>
                    <div className="font-mono-tech text-[10px] text-[var(--sa-muted)]">{h.roll_number}</div>
                  </div>
                  <div className={`font-mono-tech text-[10px] uppercase ${h.already ? "text-[var(--sa-warning)]" : "text-[var(--sa-success)]"}`}>
                    {h.already ? "Dupe" : "New"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
