/**
 * Robust webcam access utility with clear error mapping.
 * Returns { stream } on success or throws an Error with .code and .message.
 */
export async function openCamera({ width = 640, height = 480 } = {}) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const err = new Error("Your browser does not support camera access. Please use Chrome, Edge, Firefox or Safari on a device with a camera.");
    err.code = "UNSUPPORTED";
    throw err;
  }
  if (window.isSecureContext === false) {
    const err = new Error("Camera requires HTTPS. Please open the app via a secure (https://) URL.");
    err.code = "INSECURE_CONTEXT";
    throw err;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: width }, height: { ideal: height }, facingMode: "user" },
      audio: false,
    });
    return { stream };
  } catch (raw) {
    const name = raw?.name || "";
    const err = new Error("");
    err.raw = raw;
    if (name === "NotAllowedError" || name === "SecurityError") {
      err.code = "PERMISSION_DENIED";
      err.message = "Camera permission was denied. Click the camera icon in your browser address bar and allow camera access, then reload this page.";
    } else if (name === "NotFoundError" || name === "OverconstrainedError" || name === "DevicesNotFoundError") {
      err.code = "NO_DEVICE";
      err.message = "No camera device was found. Please connect a webcam and try again.";
    } else if (name === "NotReadableError" || name === "TrackStartError") {
      err.code = "IN_USE";
      err.message = "Camera is already in use by another application. Close other apps (Zoom, Meet, etc.) and try again.";
    } else if (name === "AbortError") {
      err.code = "ABORTED";
      err.message = "Camera access was aborted. Please try again.";
    } else {
      err.code = "UNKNOWN";
      err.message = `Failed to open camera: ${raw?.message || name || "Unknown error"}`;
    }
    throw err;
  }
}

export function stopStream(stream) {
  try {
    if (stream && stream.getTracks) stream.getTracks().forEach((t) => t.stop());
  } catch {
    // ignore
  }
}
