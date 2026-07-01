import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { loadFaceModels, detectFaceDescriptor, drawBox, captureFrameAsDataUrl } from "@/lib/faceApi";
import { openCamera, stopStream } from "@/lib/camera";
import { Camera, ArrowLeft, CheckCircle, XCircle } from "@phosphor-icons/react";

export default function EnrollFace() {
  const { id } = useParams();
  const nav = useNavigate();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const streamRef = useRef(null);
  const [student, setStudent] = useState(null);
  const [modelsReady, setModelsReady] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [detected, setDetected] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("Loading AI models…");
  const [cameraError, setCameraError] = useState(null);

  useEffect(() => {
    api.get(`/students/${id}`).then(r => setStudent(r.data));
    loadFaceModels().then(() => { setModelsReady(true); setStatus("Models ready. Start camera to begin."); })
      .catch(() => setStatus("Failed to load models. Refresh."));
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const start = async () => {
    setCameraError(null);
    try {
      const { stream } = await openCamera({ width: 640, height: 480 });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setStreaming(true);
      setStatus("Position face inside the frame…");
      loop();
    } catch (e) {
      setCameraError({ code: e.code, message: e.message });
      toast.error(e.message || "Cannot access camera");
    }
  };

  const stop = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    stopStream(streamRef.current);
    streamRef.current = null;
    setStreaming(false);
  };

  const loop = async () => {
    if (!videoRef.current || !modelsReady) { rafRef.current = requestAnimationFrame(loop); return; }
    const r = await detectFaceDescriptor(videoRef.current);
    drawBox(canvasRef.current, videoRef.current, r?.box, r ? "#10B981" : "#EF4444");
    setDetected(!!r);
    setStatus(r ? "Face detected. Click Capture & Enroll." : "No face detected. Adjust lighting.");
    rafRef.current = requestAnimationFrame(loop);
  };

  const capture = async () => {
    setSaving(true);
    try {
      const r = await detectFaceDescriptor(videoRef.current);
      if (!r) { toast.error("No face detected. Try again."); return; }
      const img = captureFrameAsDataUrl(videoRef.current);
      await api.post(`/students/${id}/face`, { descriptor: r.descriptor, image_base64: img });
      toast.success("Face enrolled successfully");
      stop();
      nav("/students");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Enroll failed");
    } finally { setSaving(false); }
  };

  return (
    <div className="max-w-4xl" data-testid="enroll-face-page">
      <Link to="/students" className="inline-flex items-center gap-1 text-sm text-[var(--sa-muted)] hover:text-[var(--sa-primary)] mb-4">
        <ArrowLeft size={14} /> Back to Students
      </Link>
      <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)] mb-2">// FACE ENROLLMENT</div>
      <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-1">
        Enroll Face {student && `— ${student.name}`}
      </h1>
      <p className="text-sm text-[var(--sa-muted)] mb-6">
        Capture the student&apos;s face to generate a unique AI signature (128-D descriptor).
      </p>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2 border border-black bg-black relative overflow-hidden tech-grid rounded-md">
          <video ref={videoRef} className="w-full block" muted playsInline />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
          {streaming && <div className={`scan-line ${detected ? "success" : ""}`} />}
          {!streaming && (
            <div className="aspect-[4/3] flex items-center justify-center text-white/60 font-mono-tech text-sm">
              CAMERA OFFLINE
            </div>
          )}
          <div className="absolute bottom-0 left-0 right-0 px-4 py-2 bg-black/70 text-white font-mono-tech text-[11px] tracking-widest uppercase">
            {status}
          </div>
        </div>
        <div className="space-y-3">
          {cameraError && (
            <div className="p-4 border border-[var(--sa-danger)]/40 bg-[var(--sa-danger)]/10 rounded-md" data-testid="enroll-camera-error">
              <div className="flex items-center gap-2 text-[var(--sa-danger)] font-mono-tech text-[11px] uppercase tracking-widest mb-1">
                <XCircle size={14} weight="fill" /> {cameraError.code}
              </div>
              <div className="text-sm text-[var(--sa-text)]">{cameraError.message}</div>
              <button onClick={start} className="mt-3 w-full border border-[var(--sa-border)] hover:bg-white py-2 rounded-md text-sm">Retry</button>
            </div>
          )}
          {!streaming ? (
            <button data-testid="start-camera-button" onClick={start} disabled={!modelsReady} className="w-full bg-[var(--sa-primary)] hover:bg-[var(--sa-primary-hover)] text-white font-medium py-2.5 rounded-md disabled:opacity-60 flex items-center justify-center gap-2">
              <Camera size={16} weight="bold" /> Start Camera
            </button>
          ) : (
            <>
              <button data-testid="capture-face-button" onClick={capture} disabled={!detected || saving} className="w-full bg-[var(--sa-success)] hover:opacity-90 text-white font-medium py-2.5 rounded-md disabled:opacity-60 flex items-center justify-center gap-2">
                <CheckCircle size={16} weight="bold" /> {saving ? "Enrolling…" : "Capture & Enroll"}
              </button>
              <button onClick={stop} className="w-full border border-[var(--sa-border)] hover:bg-[var(--sa-surface)] py-2.5 rounded-md text-sm">Stop Camera</button>
            </>
          )}
          <div className="bg-[var(--sa-surface)] border border-[var(--sa-border)] p-4 rounded-md text-xs text-[var(--sa-muted)] space-y-1">
            <div className="font-mono-tech uppercase tracking-widest text-[10px] mb-2 text-[var(--sa-text)]">Tips</div>
            <div>· Face the camera directly</div>
            <div>· Ensure good lighting</div>
            <div>· Remove sunglasses / masks</div>
            <div>· Keep only one face in frame</div>
          </div>
        </div>
      </div>
    </div>
  );
}
